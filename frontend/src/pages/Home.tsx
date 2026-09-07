import { useMemo, useState, type CSSProperties } from "react";

import {
  correlateSubject,
  confirmCorrelatedIdentity,
  investigateSubject,
  resolveSubjectIdentity,
  searchIdentities,
  selectIdentity,
  type LinkedSubjectIdentity,
  type ProviderIdentityCandidate,
} from "../lib/api";

import AppShell from "../components/layout/AppShell";
import InvestigationHero from "../components/investigation/InvestigationHero";
import InvestigationInput from "../components/investigation/InvestigationInput";
import ProviderCard from "../components/providers/ProviderCard";
import ProviderReport from "../components/providers/ProviderReport";
import MatrixRain from "../components/ui/MatrixRain";
import StatusBadge from "../components/ui/StatusBadge";
import GlassButton from "../components/ui/GlassButton";

import type {
  ProviderRun,
} from "../types/investigation";

import type {
  IdentityCandidate,
  SubjectInvestigationResult,
} from "../types/identity";


type Phase =
  | "idle"
  | "discovering"
  | "selecting"
  | "linking"
  | "running"
  | "complete"
  | "error";


const providers = [
  {
    id: "github",
    name: "GitHub",
    description:
      "Public profile and developer footprint.",
  },
  {
    id: "steam",
    name: "Steam",
    description:
      "Public gaming identity and activity signals.",
  },
  {
    id: "twitch",
    name: "Twitch",
    description:
      "Public creator and channel footprint.",
  },
  {
    id: "stackexchange",
    name: "Stack Exchange",
    description:
      "Public technical profile and contribution signals.",
  },
];


function observationCount(
  result?: SubjectInvestigationResult,
): number {
  return result?.observations?.length ?? 0;
}


function getProviderResult(
  results: SubjectInvestigationResult[],
  providerId: string,
): SubjectInvestigationResult | undefined {
  return results.find(
    (result) =>
      result.provider.toLowerCase() ===
      providerId.toLowerCase(),
  );
}


function confidenceFromResults(
  results: SubjectInvestigationResult[],
): string {
  const values = results.flatMap(
    (result) =>
      result.observations
        .map((observation) =>
          String(
            observation.confidence ?? "",
          ).toUpperCase(),
        )
        .filter(Boolean),
  );

  if (values.length === 0) {
    return "—";
  }

  if (
    values.every(
      (value) => value === "HIGH",
    )
  ) {
    return "HIGH";
  }

  if (
    values.some(
      (value) => value === "HIGH",
    )
  ) {
    return "MIXED";
  }

  return values[0] ?? "—";
}


function resultToProviderRun(
  result: SubjectInvestigationResult,
): ProviderRun {
  const firstError =
    result.errors[0];

  return {
    id: crypto.randomUUID(),

    provider_name:
      result.provider,

    status:
      result.status as ProviderRun["status"],

    result: {
      observations:
        result.observations,
    },

    error_code:
      firstError
        ? String(
            firstError.code ??
              firstError.error_code ??
              "PROVIDER_ERROR",
          )
        : null,

    error_message:
      firstError
        ? String(
            firstError.message ??
              firstError.error_message ??
              "Provider returned an error.",
          )
        : null,

    started_at: null,
    completed_at: null,
  };
}


export default function Home() {
  const [
    target,
    setTarget,
  ] = useState("");

  const [
    phase,
    setPhase,
  ] = useState<Phase>("idle");

  const [
    candidates,
    setCandidates,
  ] = useState<IdentityCandidate[]>([]);

  const [
    selectedCandidate,
    setSelectedCandidate,
  ] =
    useState<IdentityCandidate | null>(
      null,
    );

  const [
    providerResults,
    setProviderResults,
  ] =
    useState<
      SubjectInvestigationResult[]
    >([]);

  const [
    selectedProvider,
    setSelectedProvider,
  ] =
    useState<string | null>(
      null,
    );

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null,
    );


  const [
    subjectId,
    setSubjectId,
  ] = useState<string | null>(null);

  const [
    linkedIdentities,
    setLinkedIdentities,
  ] = useState<LinkedSubjectIdentity[]>([]);

  const linkedIdentityCount =
    linkedIdentities.length;

  const [
    providerQueries,
    setProviderQueries,
  ] = useState<Record<string, string>>({});

  const [
    providerCandidates,
    setProviderCandidates,
  ] = useState<Record<string, ProviderIdentityCandidate[]>>({});

  const [
    resolvingProvider,
    setResolvingProvider,
  ] = useState<string | null>(null);


  const running =
    phase === "discovering" ||
    phase === "running";


  const totalObservations =
    useMemo(
      () =>
        providerResults.reduce(
          (total, result) =>
            total +
            observationCount(
              result,
            ),
          0,
        ),
      [providerResults],
    );


  const identityCount =
    useMemo(
      () =>
        providerResults.filter(
          (result) =>
            observationCount(
              result,
            ) > 0,
        ).length,
      [providerResults],
    );


  const confidence =
    useMemo(
      () =>
        confidenceFromResults(
          providerResults,
        ),
      [providerResults],
    );


  /* =======================================================
   * STEP 1
   *
   * Name/query
   *      ↓
   * public identity candidates
   * ======================================================= */

  const beginInvestigation =
    async () => {
      const query =
        target.trim();

      if (
        !query ||
        running
      ) {
        return;
      }

      setError(null);
      setCandidates([]);
      setSelectedCandidate(
        null,
      );
      setSelectedProvider(
        null,
      );
      setProviderResults([]);
      setPhase(
        "discovering",
      );

      try {
        const response =
          await searchIdentities(
            query,
          );

        if (
          !response.candidates ||
          response.candidates.length === 0
        ) {
          throw new Error(
            "No public identity candidates were found for this query.",
          );
        }

        setCandidates(
          response.candidates,
        );

        setPhase(
          "selecting",
        );
      } catch (
        requestError
      ) {
        const message =
          requestError instanceof Error
            ? requestError.message
            : "Identity discovery failed.";

        setError(
          message,
        );

        setPhase(
          "error",
        );
      }
    };


  /* =======================================================
   * STEP 2 + 3
   *
   * selected candidate
   *       ↓
   * persistent subject
   *       ↓
   * four-provider investigation
   * ======================================================= */

  const handleCandidateSelect =
    async (
      candidate: IdentityCandidate,
    ) => {
      if (phase !== "selecting") {
        return;
      }

      const selectionQuery = target.trim();

      if (!selectionQuery) {
        setError("Selection query cannot be empty.");
        setPhase("error");
        return;
      }

      setError(null);
      setSelectedCandidate(candidate);
      setSelectedProvider(null);
      setProviderResults([]);
      setLinkedIdentities([]);
      setProviderCandidates({});
      setProviderQueries({});

      try {
        const selected = await selectIdentity(
          candidate,
          selectionQuery,
        );

        setSubjectId(selected.subject_id);

        const anchorIdentity: LinkedSubjectIdentity = {
          id: `anchor-${selected.subject_id}`,
          subject_id: selected.subject_id,
          provider: selected.provider,
          provider_user_id: selected.provider_user_id,
          username: selected.username ?? null,
          display_name: selected.display_name ?? null,
          profile_url: selected.profile_url ?? null,
          confidence: selected.confidence ?? null,
          identifiers: selected.identifiers ?? {},
        };

        setLinkedIdentities([anchorIdentity]);

        const correlation = await correlateSubject(
          selected.subject_id,
          selectionQuery,
        );

        const autoLinkedIdentities = correlation.auto_linked
          .map((item) => item.identity)
          .filter(
            (identity) =>
              identity.provider.toLowerCase() !==
              anchorIdentity.provider.toLowerCase(),
          );

        setLinkedIdentities([
          anchorIdentity,
          ...autoLinkedIdentities,
        ]);

        const correlatedCandidates: Record<
          string,
          ProviderIdentityCandidate[]
        > = {};

        for (const provider of providers) {
          if (
            provider.id ===
            anchorIdentity.provider.toLowerCase()
          ) {
            correlatedCandidates[provider.id] = [];
            continue;
          }

          correlatedCandidates[provider.id] =
            correlation.providers[provider.id]?.candidates ?? [];
        }

        setProviderCandidates(correlatedCandidates);
        setPhase("linking");
      } catch (requestError) {
        const message =
          requestError instanceof Error
            ? requestError.message
            : "Selected identity could not be prepared.";

        setError(message);
        setPhase("error");
      }
    };

  const handleResolveProvider = async (providerId: string) => {
    if (!subjectId) return;

    const query = (providerQueries[providerId] ?? "").trim();

    if (!query) {
      setError(`Enter a ${providerId} username or identifier first.`);
      return;
    }

    setError(null);
    setResolvingProvider(providerId);

    try {
      const response = await resolveSubjectIdentity(
        subjectId,
        providerId,
        query,
      );

      if (response.resolved && response.identity) {
        setLinkedIdentities((current) => [
          ...current.filter(
            (identity) => identity.provider.toLowerCase() !== providerId,
          ),
          response.identity as LinkedSubjectIdentity,
        ]);
        setProviderCandidates((current) => ({ ...current, [providerId]: [] }));
      } else {
        setProviderCandidates((current) => ({
          ...current,
          [providerId]: response.candidates ?? [],
        }));
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : `Unable to resolve ${providerId} identity.`,
      );
    } finally {
      setResolvingProvider(null);
    }
  };

  const handleConfirmProviderCandidate = async (
    providerId: string,
    candidate: ProviderIdentityCandidate,
  ) => {
    if (!subjectId) return;

    setError(null);
    setResolvingProvider(providerId);

    try {
      const response = await confirmCorrelatedIdentity(
        subjectId,
        candidate,
      );

      setLinkedIdentities((current) => [
        ...current.filter(
          (identity) =>
            identity.provider.toLowerCase() !== providerId,
        ),
        response.identity,
      ]);

      setProviderCandidates((current) => ({
        ...current,
        [providerId]: [],
      }));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : `Unable to link ${providerId} identity.`,
      );
    } finally {
      setResolvingProvider(null);
    }
  };

  const handleRunSubjectInvestigation = async () => {
    if (!subjectId) {
      setError("No selected subject is available for investigation.");
      return;
    }

    setError(null);
    setProviderResults([]);
    setSelectedProvider(null);
    setPhase("running");

    try {
      const investigation = await investigateSubject(subjectId);
      setProviderResults(investigation.provider_results ?? []);
      setPhase("complete");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Subject investigation failed.",
      );
      setPhase("error");
    }
  };


  /* =======================================================
   * BACK TO DISCOVERED IDENTITIES
   * ======================================================= */

  const handleBackToIdentities =
    () => {
      setError(null);

      setSelectedProvider(
        null,
      );

      setSelectedCandidate(
        null,
      );

      setProviderResults(
        [],
      );
      setSubjectId(null);
      setLinkedIdentities([]);
      setProviderQueries({});
      setProviderCandidates({});
      setResolvingProvider(null);

      /*
       * Deliberately preserve candidates.
       *
       * The user returns to the already-discovered identity
       * list without executing discovery again.
       */
      setPhase(
        "selecting",
      );
    };


  /* =======================================================
   * JSON REPORT EXPORT
   * ======================================================= */

  const handleDownloadJsonReport =
    () => {
      if (
        phase !== "complete" ||
        !selectedCandidate ||
        providerResults.length === 0
      ) {
        return;
      }

      const successfulProviders =
        providerResults.filter(
          (result) =>
            result.status ===
            "SUCCESS",
        ).length;

      const providersWithEvidence =
        providerResults.filter(
          (result) =>
            observationCount(
              result,
            ) > 0,
        ).length;

      const failedProviders =
        providerResults.filter(
          (result) =>
            [
              "FAILED",
              "TIMEOUT",
              "RATE_LIMITED",
            ].includes(
              result.status,
            ),
        ).length;

      const notFoundProviders =
        providerResults.filter(
          (result) =>
            result.status ===
            "NOT_FOUND",
        ).length;

      const skippedProviders =
        providerResults.filter(
          (result) =>
            result.status ===
            "SKIPPED",
        ).length;


      const report = {
        report_version:
          "1.0",

        generated_at:
          new Date()
            .toISOString(),

        generator: {
          application:
            "Digital Footprint Tracer",

          format:
            "JSON",
        },

        query:
          target.trim(),

        selected_identity: {
          provider:
            selectedCandidate.provider,

          provider_user_id:
            selectedCandidate.provider_user_id,

          username:
            selectedCandidate.username ??
            null,

          display_name:
            selectedCandidate.display_name ??
            null,

          profile_url:
            selectedCandidate.profile_url ??
            null,

          avatar_url:
            selectedCandidate.avatar_url ??
            null,

          confidence_score:
            selectedCandidate.score,

          confidence_percent:
            selectedCandidate.confidence_percent,

          match_type:
            selectedCandidate.match_type,

          reasons:
            selectedCandidate.reasons,

          identifiers:
            selectedCandidate.identifiers,

          public_profile_metadata: {
            public_repos:
              selectedCandidate.public_repos ??
              null,

            followers:
              selectedCandidate.followers ??
              null,

            following:
              selectedCandidate.following ??
              null,

            bio:
              selectedCandidate.bio ??
              null,

            location:
              selectedCandidate.location ??
              null,

            company:
              selectedCandidate.company ??
              null,

            blog:
              selectedCandidate.blog ??
              null,
          },
        },

        identity_correlation: {
          subject_id:
            subjectId,

          anchor_provider:
            selectedCandidate.provider,

          linked_identity_count:
            linkedIdentities.length,

          linked_identities:
            linkedIdentities.map(
              (identity) => ({
                provider:
                  identity.provider,

                provider_user_id:
                  identity.provider_user_id,

                username:
                  identity.username ??
                  null,

                display_name:
                  identity.display_name ??
                  null,

                profile_url:
                  identity.profile_url ??
                  null,

                confidence:
                  identity.confidence ??
                  null,

                identifiers:
                  identity.identifiers ??
                  {},
              }),
            ),

          unresolved_providers:
            providers
              .filter(
                (provider) =>
                  !linkedIdentities.some(
                    (identity) =>
                      identity.provider.toLowerCase() ===
                      provider.id,
                  ),
              )
              .map(
                (provider) =>
                  provider.id,
              ),
        },

        summary: {
          providers_requested:
            providers.length,

          providers_returned:
            providerResults.length,

          successful_providers:
            successfulProviders,

          providers_with_evidence:
            providersWithEvidence,

          not_found_providers:
            notFoundProviders,

          failed_providers:
            failedProviders,

          skipped_providers:
            skippedProviders,

          total_observations:
            totalObservations,

          overall_confidence:
            confidence,
        },

        providers:
          providerResults.map(
            (result) => ({
              provider:
                result.provider,

              status:
                result.status,

              supported:
                result.supported,

              executed:
                result.executed,

              requested_capabilities:
                result.requested_capabilities,

              executed_capabilities:
                result.executed_capabilities,

              observation_count:
                observationCount(
                  result,
                ),

              observations:
                result.observations,

              errors:
                result.errors,
            }),
          ),
      };


      const json =
        JSON.stringify(
          report,
          null,
          2,
        );


      const blob =
        new Blob(
          [json],
          {
            type:
              "application/json;charset=utf-8",
          },
        );


      const url =
        URL.createObjectURL(
          blob,
        );


      const rawName =
        selectedCandidate.username ??
        selectedCandidate.display_name ??
        target ??
        "subject";


      const safeName =
        rawName
          .trim()
          .toLowerCase()
          .replace(
            /[^a-z0-9]+/g,
            "-",
          )
          .replace(
            /^-+|-+$/g,
            "",
          )
          .slice(
            0,
            80,
          ) ||
        "subject";


      const date =
        new Date()
          .toISOString()
          .slice(
            0,
            10,
          );


      const anchor =
        document.createElement(
          "a",
        );

      anchor.href =
        url;

      anchor.download =
        `digital-footprint-${safeName}-${date}.json`;


      document.body.appendChild(
        anchor,
      );

      anchor.click();

      document.body.removeChild(
        anchor,
      );

      URL.revokeObjectURL(
        url,
      );
    };


  /* =======================================================
   * SELECTED PROVIDER REPORT
   * ======================================================= */

  const selectedProviderData =
    providers.find(
      (provider) =>
        provider.id ===
        selectedProvider,
    );


  const selectedProviderResult =
    selectedProvider
      ? getProviderResult(
          providerResults,
          selectedProvider,
        )
      : undefined;


  const selectedProviderRun =
    selectedProviderResult
      ? resultToProviderRun(
          selectedProviderResult,
        )
      : undefined;


  const selectedTarget =
    selectedCandidate?.username ??
    selectedCandidate?.display_name ??
    target;


  return (
    <AppShell>
      <MatrixRain
        active={phase === "discovering"}
      />

      <div className="page-container">
        <InvestigationHero
          running={running}
        />

        <InvestigationInput
          value={target}
          setValue={setTarget}
          running={running}
          onInvestigate={
            beginInvestigation
          }
        />


        {/* ================= ERROR ================= */}

        {error && (
          <section className="investigation-panel glass">
            <div className="investigation-panel__header">
              <div>
                <div className="section-label">
                  INVESTIGATION ERROR
                </div>

                <h2>
                  Trace could not be completed.
                </h2>
              </div>

              <StatusBadge status="warning">
                Failed
              </StatusBadge>
            </div>

            <div className="scan-console mono">
              <span>
                [ERR]
              </span>{" "}
              {error}
            </div>
          </section>
        )}


        {/* ============== DISCOVERING ============== */}

        {phase === "discovering" && (
          <section className="investigation-panel glass">
            <div className="investigation-panel__header">
              <div>
                <div className="section-label">
                  IDENTITY DISCOVERY
                </div>

                <h2>
                  Mapping the footprint.
                </h2>
              </div>

              <StatusBadge status="active">
                Scanning
              </StatusBadge>
            </div>

            <div className="scan-console mono">
              <span>[01]</span>{" "}
              searching public identity sources...
              <br />

              <span>[02]</span>{" "}
              resolving candidate profiles...
              <br />

              <span>[03]</span>{" "}
              ranking identity matches...
            </div>
          </section>
        )}


        {/* =============== SELECTING =============== */}

        {phase === "selecting" && (
          <section className="investigation-panel glass">
            <div className="investigation-panel__header">
              <div>
                <div className="section-label">
                  IDENTITY DISCOVERY
                </div>

                <h2>
                  Select the identity.
                </h2>
              </div>

              <StatusBadge status="active">
                {`${candidates.length} ${
                  candidates.length === 1
                    ? "match"
                    : "matches"
                }`}
              </StatusBadge>
            </div>

            <div className="target-chip mono">
              <span className="target-chip__prefix">
                QUERY =
              </span>

              <strong>
                {target}
              </strong>
            </div>

            <div className="provider-grid">
              {candidates.map(
                (candidate) => (
                  <article
                    key={`${candidate.provider}-${candidate.provider_user_id}`}
                    className="provider-card provider-card--complete provider-card--clickable"
                    onClick={() =>
                      handleCandidateSelect(
                        candidate,
                      )
                    }
                  >
                    <div className="provider-card__reflection" />

                    <div className="provider-card__top">
                      <div className="provider-card__icon">
                        {candidate.provider
                          .slice(0, 2)
                          .toUpperCase()}
                      </div>

                      <span className="provider-card__status">
                        {Math.round(
                          candidate.confidence_percent,
                        )}
                        % MATCH
                      </span>
                    </div>

                    <div className="provider-card__name">
                      {candidate.display_name ??
                        candidate.username ??
                        candidate.provider_user_id}
                    </div>

                    <div className="provider-card__description">
                      <strong>
                        {candidate.username ??
                          candidate.provider_user_id}
                      </strong>

                      <br />

                      {candidate.provider}
                      {" · "}
                      {candidate.match_type.replace(
                        /_/g,
                        " ",
                      )}
                    </div>

                    <div className="provider-card__hint">
                      Select identity →
                    </div>

                    <div className="provider-card__line">
                      <span />
                    </div>
                  </article>
                ),
              )}
            </div>

            <div className="scan-console mono">
              <span>[01]</span>{" "}
              public identities discovered...
              <br />

              <span>[02]</span>{" "}
              candidate relevance scored...
              <br />

              <span>[03]</span>{" "}
              awaiting operator selection...
            </div>
          </section>
        )}


        {/* ============ PROVIDER IDENTITY LINKING ============ */}

        {["linking", "running", "complete"].includes(phase) &&
          selectedCandidate &&
          subjectId && (
          <section className="investigation-panel glass">
            <div className="investigation-panel__header">
              <div>
                <div className="section-label">IDENTITY CORRELATION</div>
                <h2>Correlated provider identities.</h2>
              </div>

              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                <GlassButton variant="secondary" onClick={handleBackToIdentities}>
                  ← Back to identities
                </GlassButton>
                <StatusBadge status="active">
  {`${linkedIdentityCount} linked`}
</StatusBadge>
              </div>
            </div>

            <div className="target-chip mono">
              <span className="target-chip__prefix">SUBJECT =</span>
              <strong>
                {selectedCandidate.display_name ??
                  selectedCandidate.username ??
                  target}
              </strong>
            </div>

            <div className="provider-grid">
              {providers.map((provider, index) => {
                const linked = linkedIdentities.find(
                  (identity) =>
                    identity.provider.toLowerCase() === provider.id,
                );
                const isAnchor =
                  selectedCandidate.provider.toLowerCase() === provider.id;
                const possible = providerCandidates[provider.id] ?? [];
                const busy = resolvingProvider === provider.id;

                return (
                  <article
                    key={provider.id}
                    className="provider-card provider-card--complete"
                    style={{ "--provider-delay": `${index * 90}ms` } as CSSProperties}
                  >
                    <div className="provider-card__reflection" />

                    <div className="provider-card__top">
                      <div className="provider-card__icon">
                        {provider.name.slice(0, 2).toUpperCase()}
                      </div>
                      <span className="provider-card__status">
                        {linked
                          ? isAnchor
                            ? "VERIFIED"
                            : "LINKED"
                          : busy
                            ? "RESOLVING"
                            : possible.length > 0
                              ? `${possible.length} POSSIBLE`
                              : "UNRESOLVED"}
                      </span>
                    </div>

                    <div className="provider-card__name">{provider.name}</div>

                    <div className="provider-card__description">
                      {linked ? (
                        <>
                          <strong>
                            {linked.username ??
                              linked.display_name ??
                              linked.provider_user_id}
                          </strong>
                          <br />
                          {isAnchor
                            ? "Selected anchor identity"
                            : "Automatically verified provider identity"}
                        </>
                      ) : possible.length > 0 ? (
                        <>
                          {possible.slice(0, 5).map((candidate) => (
                            <button
                              key={candidate.provider_user_id}
                              type="button"
                              onClick={() =>
                                handleConfirmProviderCandidate(
                                  provider.id,
                                  candidate,
                                )
                              }
                              disabled={busy}
                              style={{
                                width: "100%",
                                textAlign: "left",
                                marginTop: "8px",
                                padding: "10px 11px",
                                borderRadius: "9px",
                                border: "1px solid rgba(109,255,174,.15)",
                                background: "rgba(0,0,0,.18)",
                                color: "inherit",
                                cursor: busy ? "wait" : "pointer",
                              }}
                            >
                              <strong>
                                {candidate.username ??
                                  candidate.display_name ??
                                  candidate.provider_user_id}
                              </strong>
                              <br />
                              <small>
                                {candidate.correlation_percent ??
                                  Math.round(candidate.confidence * 100)}
                                % correlation · Confirm identity →
                              </small>
                            </button>
                          ))}
                        </>
                      ) : (
                        <span>No reliable correlated identity found.</span>
                      )}
                    </div>

                    {!linked && !isAnchor && (
                      <div style={{ marginTop: "14px" }}>
                        <small style={{ display: "block", opacity: 0.7 }}>
                          {possible.length > 0
                            ? "None of these? Add a known provider identity."
                            : "Know this provider identity? Add it as a fallback."}
                        </small>

                        <input
                          value={providerQueries[provider.id] ?? ""}
                          onChange={(event) =>
                            setProviderQueries((current) => ({
                              ...current,
                              [provider.id]: event.target.value,
                            }))
                          }
                          placeholder={
                            provider.id === "twitch"
                              ? "Twitch username or channel"
                              : provider.id === "steam"
                                ? "SteamID64, vanity name, or profile URL"
                                : provider.id === "stackexchange"
                                  ? "Stack Exchange profile URL or site:user_id"
                                  : "Provider username"
                          }
                          disabled={busy}
                          style={{
                            width: "100%",
                            boxSizing: "border-box",
                            marginTop: "8px",
                            padding: "11px 12px",
                            borderRadius: "10px",
                            border: "1px solid rgba(109,255,174,.18)",
                            background: "rgba(0,0,0,.22)",
                            color: "inherit",
                          }}
                        />

                        <button
                          type="button"
                          onClick={() => handleResolveProvider(provider.id)}
                          disabled={busy}
                          style={{
                            marginTop: "10px",
                            border: 0,
                            background: "transparent",
                            color: "#6dffae",
                            padding: 0,
                            cursor: busy ? "wait" : "pointer",
                            font: "inherit",
                            fontWeight: 700,
                          }}
                        >
                          {busy ? "Resolving…" : "Resolve known identity →"}
                        </button>
                      </div>
                    )}

                    <div className="provider-card__line">
                      <span />
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="scan-console mono">
              <span>[01]</span> verified anchor locked...<br />
              <span>[02]</span> reusable public signals expanded...<br />
              <span>[03]</span> cross-provider candidates discovered and scored...<br />
              <span>[04]</span> ambiguous identities require operator confirmation...
            </div>

            <div
              style={{
                marginTop: "18px",
                display: "flex",
                justifyContent: "flex-end",
              }}
            >
              {phase === "linking" ? (
                <GlassButton onClick={handleRunSubjectInvestigation}>
                  Start Investigation →
                </GlassButton>
              ) : (
                <StatusBadge
                  status={phase === "complete" ? "success" : "active"}
                >
                  {phase === "complete"
                    ? "Investigation complete"
                    : "Investigation running"}
                </StatusBadge>
              )}
            </div>
          </section>
        )}

        {/* ============ INVESTIGATION ============ */}

        {["linking", "running", "complete"].includes(phase) && (
          <section
            className={`investigation-panel glass ${
              selectedProvider
                ? "investigation-panel--report-open"
                : ""
            }`}
          >
            {!selectedProvider ? (
              <>
                <div className="investigation-panel__header">
                  <div>
                    <div className="section-label">
                      INVESTIGATION ENGINE
                    </div>

                    <h2>
                      {phase === "complete"
                        ? "Footprint assembled."
                        : phase === "running"
                          ? "Tracing public signals."
                          : "Provider execution ready."}
                    </h2>
                  </div>

                  <div
                    style={{
                      display:
                        "flex",

                      alignItems:
                        "center",

                      gap:
                        "12px",

                      flexWrap:
                        "wrap",

                      justifyContent:
                        "flex-end",
                    }}
                  >
                    {phase ===
                      "complete" && (
                      <GlassButton
                        variant="secondary"
                        onClick={
                          handleBackToIdentities
                        }
                      >
                        ← Back to identities
                      </GlassButton>
                    )}

                    {phase ===
                      "complete" && (
                      <GlassButton
                        variant="secondary"
                        onClick={
                          handleDownloadJsonReport
                        }
                      >
                        ↓ Download JSON Report
                      </GlassButton>
                    )}

                    <StatusBadge
                      status={
                        phase === "complete"
                          ? "success"
                          : "active"
                      }
                    >
                      {phase === "complete"
                        ? "Complete"
                        : phase === "running"
                          ? "Running"
                          : "Ready"}
                    </StatusBadge>
                  </div>
                </div>


                <div className="target-chip mono">
                  <span className="target-chip__prefix">
                    TARGET =
                  </span>

                  <strong>
                    {selectedTarget}
                  </strong>
                </div>


                <div className="provider-grid">
                  {providers.map(
                    (
                      provider,
                      index,
                    ) => {
                      const result =
                        getProviderResult(
                          providerResults,
                          provider.id,
                        );

                      const terminal =
                        Boolean(
                          result &&
                            [
                              "SUCCESS",
                              "NOT_FOUND",
                              "RATE_LIMITED",
                              "TIMEOUT",
                              "FAILED",
                              "SKIPPED",
                            ].includes(
                              result.status,
                            ),
                        );

                      return (
                        <ProviderCard
                          key={
                            provider.id
                          }
                          name={
                            provider.name
                          }
                          description={
                            provider.description
                          }
                          status={
                            terminal
                              ? "complete"
                              : phase ===
                                  "running"
                                ? "running"
                                : "idle"
                          }
                          resultStatus={
                            result?.status
                          }
                          observationCount={
                            observationCount(
                              result,
                            )
                          }
                          index={
                            index
                          }
                          onOpenReport={
                            result
                              ? () =>
                                  setSelectedProvider(
                                    provider.id,
                                  )
                              : undefined
                          }
                        />
                      );
                    },
                  )}
                </div>


                {phase === "running" ? (
                  <div className="scan-console mono">
                    <span>[01]</span>{" "}
                    selected identity locked...
                    <br />

                    <span>[02]</span>{" "}
                    executing provider enrichment...
                    <br />

                    <span>[03]</span>{" "}
                    collecting public observations...
                    <br />

                    <span>[04]</span>{" "}
                    correlating available evidence...
                  </div>
                ) : phase === "complete" ? (
                  <div className="evidence-preview">
                    <div className="evidence-preview__top">
                      <div>
                        <div className="section-label">
                          EVIDENCE SURFACE
                        </div>

                        <h3>
                          Correlated public identity signals
                        </h3>
                      </div>

                      <span className="mono evidence-preview__code">
                        DFT://EVIDENCE
                      </span>
                    </div>


                    <div className="evidence-grid">
                      <div className="evidence-card">
                        <span>
                          IDENTITIES
                        </span>

                        <strong>
                          {identityCount}
                        </strong>

                        <small>
                          provider-linked signals
                        </small>
                      </div>


                      <div className="evidence-card">
                        <span>
                          OBSERVATIONS
                        </span>

                        <strong>
                          {totalObservations}
                        </strong>

                        <small>
                          public observations
                        </small>
                      </div>


                      <div className="evidence-card">
                        <span>
                          CONFIDENCE
                        </span>

                        <strong>
                          {confidence}
                        </strong>

                        <small>
                          observed confidence
                        </small>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="scan-console mono">
                    <span>[READY]</span>{" "}
                    linked identities are locked; start investigation when ready.
                  </div>
                )}
              </>
            ) : (
              selectedProviderData &&
              selectedProviderRun ? (
                <ProviderReport
                  name={
                    selectedProviderData.name
                  }
                  description={
                    selectedProviderData.description
                  }
                  target={
                    selectedTarget
                  }
                  run={
                    selectedProviderRun
                  }
                  onClose={() =>
                    setSelectedProvider(
                      null,
                    )
                  }
                />
              ) : null
            )}
          </section>
        )}
      </div>
    </AppShell>
  );
}
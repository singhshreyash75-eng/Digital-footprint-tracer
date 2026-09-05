import { useMemo, useState } from "react";

import {
  investigateSubject,
  searchIdentities,
  selectIdentity,
} from "../lib/api";

import AppShell from "../components/layout/AppShell";
import InvestigationHero from "../components/investigation/InvestigationHero";
import InvestigationInput from "../components/investigation/InvestigationInput";
import ProviderCard from "../components/providers/ProviderCard";
import ProviderReport from "../components/providers/ProviderReport";
import MatrixRain from "../components/ui/MatrixRain";
import StatusBadge from "../components/ui/StatusBadge";

import type { ProviderRun } from "../types/investigation";

import type {
  IdentityCandidate,
  SubjectInvestigationResult,
} from "../types/identity";

type Phase =
  | "idle"
  | "discovering"
  | "selecting"
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
  const values = results.flatMap((result) =>
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
  const firstError = result.errors[0];

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
  const [target, setTarget] =
    useState("");

  const [phase, setPhase] =
    useState<Phase>("idle");

  const [candidates, setCandidates] =
    useState<IdentityCandidate[]>([]);

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
  ] = useState<
    SubjectInvestigationResult[]
  >([]);

  const [
    selectedProvider,
    setSelectedProvider,
  ] =
    useState<string | null>(null);

  const [error, setError] =
    useState<string | null>(null);

  const running =
    phase === "discovering" ||
    phase === "running";

  const totalObservations =
    useMemo(
      () =>
        providerResults.reduce(
          (total, result) =>
            total +
            observationCount(result),
          0,
        ),
      [providerResults],
    );

  const identityCount =
    useMemo(
      () =>
        providerResults.filter(
          (result) =>
            observationCount(result) > 0,
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
   * Name -> candidate discovery
   * ======================================================= */

  const beginInvestigation =
    async () => {
      const query = target.trim();

      if (!query || running) {
        return;
      }

      setError(null);
      setCandidates([]);
      setSelectedCandidate(null);
      setSelectedProvider(null);
      setProviderResults([]);
      setPhase("discovering");

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

        setPhase("selecting");
      } catch (requestError) {
        const message =
          requestError instanceof Error
            ? requestError.message
            : "Identity discovery failed.";

        setError(message);
        setPhase("error");
      }
    };

  /* =======================================================
   * STEP 2 + 3
   *
   * candidate
   *    ↓
   * subject_id
   *    ↓
   * four-provider investigation
   * ======================================================= */

  const handleCandidateSelect =
    async (
      candidate: IdentityCandidate,
    ) => {
      if (phase !== "selecting") {
        return;
      }

      setError(null);
      setSelectedCandidate(
        candidate,
      );
      setSelectedProvider(null);
      setProviderResults([]);
      setPhase("running");

      try {
        const selected =
          await selectIdentity(
            candidate,
          );

        const investigation =
          await investigateSubject(
            selected.subject_id,
          );

        setProviderResults(
          investigation.provider_results ??
            [],
        );

        setPhase("complete");
      } catch (requestError) {
        const message =
          requestError instanceof Error
            ? requestError.message
            : "Selected identity investigation failed.";

        setError(message);
        setPhase("error");
      }
    };

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
        active={running}
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
                  Trace could not be
                  completed.
                </h2>
              </div>

              <StatusBadge status="warning">
                Failed
              </StatusBadge>
            </div>

            <div className="scan-console mono">
              <span>[ERR]</span>{" "}
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
              searching public identity
              sources...
              <br />

              <span>[02]</span>{" "}
              resolving candidate
              profiles...
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
              public identities
              discovered...
              <br />

              <span>[02]</span>{" "}
              candidate relevance
              scored...
              <br />

              <span>[03]</span>{" "}
              awaiting operator
              selection...
            </div>
          </section>
        )}

        {/* ============ INVESTIGATION ============ */}

        {(phase === "running" ||
          phase === "complete") && (
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
                      {phase ===
                      "complete"
                        ? "Footprint assembled."
                        : "Tracing public signals."}
                    </h2>
                  </div>

                  <StatusBadge
                    status={
                      phase ===
                      "complete"
                        ? "success"
                        : "active"
                    }
                  >
                    {phase ===
                    "complete"
                      ? "Complete"
                      : "Running"}
                  </StatusBadge>
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
                          observationCount={observationCount(
                            result,
                          )}
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

                {phase ===
                "running" ? (
                  <div className="scan-console mono">
                    <span>[01]</span>{" "}
                    selected identity
                    locked...
                    <br />

                    <span>[02]</span>{" "}
                    executing provider
                    enrichment...
                    <br />

                    <span>[03]</span>{" "}
                    collecting public
                    observations...
                    <br />

                    <span>[04]</span>{" "}
                    correlating available
                    evidence...
                  </div>
                ) : (
                  <div className="evidence-preview">
                    <div className="evidence-preview__top">
                      <div>
                        <div className="section-label">
                          EVIDENCE SURFACE
                        </div>

                        <h3>
                          Correlated public
                          identity signals
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
                          {
                            identityCount
                          }
                        </strong>

                        <small>
                          provider-linked
                          signals
                        </small>
                      </div>

                      <div className="evidence-card">
                        <span>
                          OBSERVATIONS
                        </span>

                        <strong>
                          {
                            totalObservations
                          }
                        </strong>

                        <small>
                          public
                          observations
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
                          observed
                          confidence
                        </small>
                      </div>
                    </div>
                  </div>
                )}
              </>
            ) : selectedProviderData &&
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
            ) : null}
          </section>
        )}
      </div>
    </AppShell>
  );
}
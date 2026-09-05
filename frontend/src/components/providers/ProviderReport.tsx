import GlassButton from "../ui/GlassButton";
import StatusBadge from "../ui/StatusBadge";
import type { ProviderObservation, ProviderRun } from "../../types/investigation";

type ProviderReportProps = {
  name: string;
  description: string;
  target: string;
  run: ProviderRun;
  onClose: () => void;
};

function stringValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function summarizeData(data: Record<string, unknown> | null | undefined) {
  if (!data) return "No structured observation data.";

  const entries = Object.entries(data).slice(0, 5);

  if (entries.length === 0) {
    return "Observation returned without structured fields.";
  }

  return entries
    .map(([key, value]) => {
      if (Array.isArray(value)) {
        return `${key}: ${value.length} item${value.length === 1 ? "" : "s"}`;
      }

      return `${key}: ${stringValue(value)}`;
    })
    .join(" · ");
}

function getProfileObservation(
  observations: ProviderObservation[],
) {
  return observations.find((observation) =>
    String(observation.type ?? "").toLowerCase().includes("profile"),
  ) ?? observations[0];
}

function confidenceLabel(observations: ProviderObservation[]) {
  const values = observations
    .map((observation) => String(observation.confidence ?? "").toUpperCase())
    .filter(Boolean);

  if (values.length === 0) return "—";
  if (values.every((value) => value === "HIGH")) return "HIGH";
  if (values.some((value) => value === "HIGH")) return "MIXED";
  if (values.some((value) => value === "DERIVED")) return "DERIVED";
  return values[0];
}

function displayStatus(status: string) {
  return status.replace(/_/g, " ");
}

export default function ProviderReport({
  name,
  description,
  target,
  run,
  onClose,
}: ProviderReportProps) {
  const observations = run.result?.observations ?? [];
  const profile = getProfileObservation(observations);
  const profileData = profile?.data ?? {};

  const identityValue =
    (profileData.username as string | undefined) ??
    (profileData.login as string | undefined) ??
    (profileData.personaname as string | undefined) ??
    target;

  const profileUrl =
    (profileData.profile_url as string | undefined) ??
    profile?.source_url ??
    null;

  const terminalStatus = displayStatus(run.status);

  return (
    <section className="provider-report">
      <div className="provider-report__reflection" />

      <div className="provider-report__header">
        <div>
          <div className="provider-report__eyebrow mono">
            DFT://EVIDENCE/{name.toUpperCase()}
          </div>
          <h3>{name}</h3>
          <p>{description}</p>
        </div>

        <StatusBadge
          status={run.status === "SUCCESS" ? "success" : "warning"}
        >
          {terminalStatus}
        </StatusBadge>
      </div>

      <div className="provider-report__target mono">
        <span>TARGET =</span>
        <strong>{target}</strong>
      </div>

      <div className="provider-report__grid">
        <div className="provider-report__identity">
          <div className="report-avatar">
            {name.slice(0, 2).toUpperCase()}
          </div>

          <div>
            <span>PUBLIC IDENTITY</span>
            <strong>{identityValue}</strong>
            {profileUrl ? (
              <a
                href={profileUrl}
                target="_blank"
                rel="noreferrer"
                className="mono"
                style={{
                  display: "block",
                  marginTop: "7px",
                  color: "#6dffae",
                  fontSize: "10px",
                  overflowWrap: "anywhere",
                }}
              >
                {profileUrl}
              </a>
            ) : null}
          </div>
        </div>

        <div className="provider-report__facts">
          <div className="report-fact">
            <span>STATUS</span>
            <strong>{terminalStatus}</strong>
          </div>

          <div className="report-fact">
            <span>OBSERVATIONS</span>
            <strong>{observations.length}</strong>
          </div>

          <div className="report-fact">
            <span>CONFIDENCE</span>
            <strong>{confidenceLabel(observations)}</strong>
          </div>

          <div className="report-fact">
            <span>ERROR</span>
            <strong>{run.error_code ?? "NONE"}</strong>
          </div>
        </div>
      </div>

      <div className="provider-report__timeline">
        <div className="timeline-line" />

        {observations.length > 0 ? (
          observations.map((observation, index) => (
            <div className="timeline-item" key={`${observation.type ?? "observation"}-${index}`}>
              <span className="timeline-node" />
              <div>
                <strong>
                  {observation.type ?? `Observation ${index + 1}`}
                </strong>
                <small>
                  {observation.source ?? name}
                  {observation.source_url
                    ? ` · ${observation.source_url}`
                    : ""}
                </small>
                <small>
                  {summarizeData(observation.data)}
                </small>
              </div>
            </div>
          ))
        ) : (
          <div className="timeline-item">
            <span className="timeline-node" />
            <div>
              <strong>No observations returned</strong>
              <small>
                {run.error_message ??
                  "The provider completed without public evidence."}
              </small>
            </div>
          </div>
        )}
      </div>

      <div className="provider-report__footer">
        <span className="mono">
          REAL PROVIDER RESULT · READ ONLY
        </span>

        <GlassButton variant="secondary" onClick={onClose}>
          Close
        </GlassButton>
      </div>
    </section>
  );
}

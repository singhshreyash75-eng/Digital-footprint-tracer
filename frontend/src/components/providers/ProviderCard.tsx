import type { CSSProperties, KeyboardEvent } from "react";

type ProviderStatus =
  | "idle"
  | "running"
  | "complete";

type ProviderCardProps = {
  name: string;
  description: string;
  status: ProviderStatus;
  resultStatus?: string;
  observationCount?: number;
  index?: number;
  onOpenReport?: () => void;
};

function formatStatus(status?: string) {
  switch (status) {
    case "SUCCESS":
      return "Complete";
    case "NOT_FOUND":
      return "Not found";
    case "RATE_LIMITED":
      return "Rate limited";
    case "TIMEOUT":
      return "Timeout";
    case "FAILED":
      return "Failed";
    case "SKIPPED":
      return "Skipped";
    case "PENDING":
      return "Queued";
    case "RUNNING":
      return "Scanning";
    default:
      return status ? status.replace(/_/g, " ") : "Ready";
  }
}

export default function ProviderCard({
  name,
  description,
  status,
  resultStatus,
  observationCount = 0,
  index = 0,
  onOpenReport,
}: ProviderCardProps) {
  const terminal = status === "complete";
  const clickable = terminal && Boolean(onOpenReport);
  const label = terminal
    ? formatStatus(resultStatus)
    : status === "running"
      ? "Scanning"
      : "Ready";

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (!clickable) return;

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenReport?.();
    }
  };

  return (
    <article
      className={[
        "provider-card",
        `provider-card--${status}`,
        clickable ? "provider-card--clickable" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{
        "--provider-delay": `${index * 90}ms`,
      } as CSSProperties}
      onClick={clickable ? onOpenReport : undefined}
      onKeyDown={handleKeyDown}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
    >
      <div className="provider-card__reflection" />

      <div className="provider-card__top">
        <div className="provider-card__icon">
          {name.slice(0, 2).toUpperCase()}
        </div>

        <span className="provider-card__status">
          {label}
        </span>
      </div>

      <div className="provider-card__name">
        {name}
      </div>

      <div className="provider-card__description">
        {description}
      </div>

      {terminal && observationCount > 0 ? (
        <div className="provider-card__hint">
          {observationCount} observation
          {observationCount === 1 ? "" : "s"} · Open report →
        </div>
      ) : terminal ? (
        <div className="provider-card__hint">
          Open report →
        </div>
      ) : null}

      <div className="provider-card__line">
        <span />
      </div>
    </article>
  );
}

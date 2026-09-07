import type {
  CSSProperties,
  KeyboardEvent,
} from "react";

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
      return status
        ? status.replace(/_/g, " ")
        : "Ready";
  }
}

function getTerminalMessage(
  resultStatus: string | undefined,
  observationCount: number,
) {
  if (
    resultStatus === "SUCCESS" &&
    observationCount === 0
  ) {
    return "No public evidence returned";
  }

  switch (resultStatus) {
    case "NOT_FOUND":
      return "No public profile found";

    case "FAILED":
      return "Provider unavailable";

    case "TIMEOUT":
      return "Provider timed out";

    case "RATE_LIMITED":
      return "Provider rate limited";

    case "SKIPPED":
      return "Provider was skipped";

    default:
      return "No public evidence returned";
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

  /*
   * A report is useful only when actual evidence exists.
   *
   * NOT_FOUND / FAILED / TIMEOUT / SKIPPED providers remain
   * visible so the operator can understand investigation
   * coverage, but they do not open an empty report.
   */
  const hasEvidence =
    terminal &&
    resultStatus === "SUCCESS" &&
    observationCount > 0;

  const clickable =
    hasEvidence &&
    Boolean(onOpenReport);

  const label = terminal
    ? formatStatus(resultStatus)
    : status === "running"
      ? "Scanning"
      : "Ready";

  const handleKeyDown = (
    event: KeyboardEvent<HTMLElement>,
  ) => {
    if (!clickable) {
      return;
    }

    if (
      event.key === "Enter" ||
      event.key === " "
    ) {
      event.preventDefault();
      onOpenReport?.();
    }
  };

  return (
    <article
      className={[
        "provider-card",
        `provider-card--${status}`,
        clickable
          ? "provider-card--clickable"
          : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={
        {
          "--provider-delay":
            `${index * 90}ms`,
        } as CSSProperties
      }
      onClick={
        clickable
          ? onOpenReport
          : undefined
      }
      onKeyDown={handleKeyDown}
      role={
        clickable
          ? "button"
          : undefined
      }
      tabIndex={
        clickable
          ? 0
          : undefined
      }
    >
      <div className="provider-card__reflection" />

      <div className="provider-card__top">
        <div className="provider-card__icon">
          {name
            .slice(0, 2)
            .toUpperCase()}
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

      {terminal ? (
        hasEvidence ? (
          <div className="provider-card__hint">
            {observationCount} observation
            {observationCount === 1
              ? ""
              : "s"}
            {" · Open report →"}
          </div>
        ) : (
          <div className="provider-card__hint">
            {getTerminalMessage(
              resultStatus,
              observationCount,
            )}
          </div>
        )
      ) : null}

      <div className="provider-card__line">
        <span />
      </div>
    </article>
  );
}
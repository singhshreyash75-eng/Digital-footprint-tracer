import type { CSSProperties } from "react";
type ProviderStatus =
  | "idle"
  | "running"
  | "complete";

type ProviderCardProps = {
  name: string;
  description: string;
  status: ProviderStatus;
  index?: number;
  onOpenReport?: () => void;
};

export default function ProviderCard({
  name,
  description,
  status,
  index = 0,
  onOpenReport,
}: ProviderCardProps) {
  const label =
    status === "running"
      ? "Scanning"
      : status === "complete"
        ? "Complete"
        : "Ready";

  const clickable =
    status === "complete" &&
    Boolean(onOpenReport);

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
      style={{
        "--provider-delay": `${index * 90}ms`,
      } as CSSProperties}
      onClick={
        clickable
          ? onOpenReport
          : undefined
      }
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
      onKeyDown={(event) => {
        if (
          clickable &&
          (event.key === "Enter" ||
            event.key === " ")
        ) {
          event.preventDefault();
          onOpenReport?.();
        }
      }}
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

      {status === "complete" && (
        <div className="provider-card__hint">
          Open report →
        </div>
      )}

      <div className="provider-card__line">
        <span />
      </div>
    </article>
  );
}
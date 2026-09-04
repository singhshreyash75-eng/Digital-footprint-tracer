import GlassButton from "../ui/GlassButton";
import StatusBadge from "../ui/StatusBadge";

type ProviderReportProps = {
  name: string;
  description: string;
  target: string;
  onClose: () => void;
};

const reportRows = [
  ["IDENTITY", "Provider-linked public profile"],
  ["SOURCE", "Public provider data"],
  ["STATUS", "Verified observation"],
  ["CONFIDENCE", "HIGH"],
] as const;

export default function ProviderReport({
  name,
  description,
  target,
  onClose,
}: ProviderReportProps) {
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

        <StatusBadge status="success">Complete</StatusBadge>
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
            <strong>{target}</strong>
          </div>
        </div>

        <div className="provider-report__facts">
          {reportRows.map(([label, value]) => (
            <div className="report-fact" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="provider-report__timeline">
        <div className="timeline-line" />

        <div className="timeline-item">
          <span className="timeline-node" />
          <div>
            <strong>Public identifier resolved</strong>
            <small>
              Identity endpoint returned a matching public record.
            </small>
          </div>
        </div>

        <div className="timeline-item">
          <span className="timeline-node" />
          <div>
            <strong>Provider observation captured</strong>
            <small>
              Observation normalized into the investigation evidence model.
            </small>
          </div>
        </div>

        <div className="timeline-item">
          <span className="timeline-node" />
          <div>
            <strong>Correlation ready</strong>
            <small>
              Available for cross-provider identity correlation.
            </small>
          </div>
        </div>
      </div>

      <div className="provider-report__footer">
        <GlassButton variant="secondary" onClick={onClose}>
          Close
        </GlassButton>
      </div>
    </section>
  );
}

import GlassButton from "../ui/GlassButton";
import GlassCard from "../ui/GlassCard";
import GlassInput from "../ui/GlassInput";

type InvestigationInputProps = {
  value: string;
  setValue: (value: string) => void;
  running: boolean;
  onInvestigate: () => void;
};

export default function InvestigationInput({
  value,
  setValue,
  running,
  onInvestigate,
}: InvestigationInputProps) {
  return (
    <GlassCard className="investigation-input">
      <div className="investigation-input__label">TARGET IDENTIFIER</div>

      <div className="investigation-input__row">
        <GlassInput
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Enter a username..."
          disabled={running}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !running) {
              onInvestigate();
            }
          }}
        />

        <GlassButton
          type="button"
          onClick={onInvestigate}
          disabled={running || !value.trim()}
        >
          {running ? "Tracing..." : "Investigate"}
          <span className="button-arrow">{running ? "•" : "→"}</span>
        </GlassButton>
      </div>

      <div className="investigation-input__footer">
        Username-based investigation · Public data only
      </div>
    </GlassCard>
  );
}
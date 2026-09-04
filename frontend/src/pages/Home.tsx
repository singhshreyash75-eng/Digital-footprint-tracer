import { useMemo, useState } from "react";

import AppShell from "../components/layout/AppShell";
import InvestigationHero from "../components/investigation/InvestigationHero";
import InvestigationInput from "../components/investigation/InvestigationInput";
import ProviderCard from "../components/providers/ProviderCard";
import ProviderReport from "../components/providers/ProviderReport";
import MatrixRain from "../components/ui/MatrixRain";
import StatusBadge from "../components/ui/StatusBadge";

type InvestigationState = "idle" | "running" | "complete";

const providers = [
  {
    name: "GitHub",
    description: "Public profile and developer footprint.",
  },
  {
    name: "Steam",
    description: "Public gaming identity and activity signals.",
  },
  {
    name: "Twitch",
    description: "Public creator and channel footprint.",
  },
  {
    name: "Stack Exchange",
    description: "Public technical profile and contribution signals.",
  },
];

export default function Home() {
  const [target, setTarget] = useState("");
  const [state, setState] = useState<InvestigationState>("idle");
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

  const running = state === "running";

  const providerStatus = useMemo(() => {
    if (state === "complete") return "complete" as const;
    if (state === "running") return "running" as const;
    return "idle" as const;
  }, [state]);

  const handleInvestigate = () => {
    if (!target.trim() || running) return;

    setSelectedProvider(null);
    setState("running");

    window.setTimeout(() => {
      setState("complete");
    }, 5200);
  };

  const selectedProviderData = providers.find(
    (provider) => provider.name === selectedProvider,
  );

  return (
    <AppShell>
      <MatrixRain active={running} />

      <div className="page-container">
        <InvestigationHero running={running} />

        <InvestigationInput
          value={target}
          setValue={setTarget}
          running={running}
          onInvestigate={handleInvestigate}
        />

        {running || state === "complete" ? (
          <section
            className={`investigation-panel glass ${
              selectedProvider ? "investigation-panel--report-open" : ""
            }`}
          >
            {!selectedProvider ? (
              <>
                <div className="investigation-panel__header">
                  <div>
                    <div className="section-label">INVESTIGATION ENGINE</div>

                    <h2>
                      {state === "complete"
                        ? "Footprint assembled."
                        : "Tracing public signals."}
                    </h2>
                  </div>

                  <StatusBadge
                    status={state === "complete" ? "success" : "active"}
                  >
                    {state === "complete" ? "Complete" : "Running"}
                  </StatusBadge>
                </div>

                <div className="target-chip mono">
                  <span className="target-chip__prefix">TARGET =</span>
                  <strong>{target}</strong>
                </div>

                <div className="provider-grid">
                  {providers.map((provider, index) => (
                    <ProviderCard
                      key={provider.name}
                      name={provider.name}
                      description={provider.description}
                      status={providerStatus}
                      index={index}
                      onOpenReport={() => setSelectedProvider(provider.name)}
                    />
                  ))}
                </div>

                {state === "complete" ? (
                  <div className="evidence-preview">
                    <div className="evidence-preview__top">
                      <div>
                        <div className="section-label">EVIDENCE SURFACE</div>
                        <h3>Correlated public identity signals</h3>
                      </div>

                      <span className="mono evidence-preview__code">
                        DFT://EVIDENCE
                      </span>
                    </div>

                    <div className="evidence-grid">
                      <div className="evidence-card">
                        <span>IDENTITIES</span>
                        <strong>04</strong>
                        <small>provider-linked signals</small>
                      </div>

                      <div className="evidence-card">
                        <span>OBSERVATIONS</span>
                        <strong>24+</strong>
                        <small>public observations</small>
                      </div>

                      <div className="evidence-card">
                        <span>CONFIDENCE</span>
                        <strong>HIGH</strong>
                        <small>correlation quality</small>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="scan-console mono">
                    <span>[01]</span> resolving public identifiers...
                    <br />
                    <span>[02]</span> querying connected sources...
                    <br />
                    <span>[03]</span> correlating observations...
                    <br />
                    <span>[04]</span> constructing evidence graph...
                  </div>
                )}
              </>
            ) : selectedProviderData ? (
              <ProviderReport
                name={selectedProviderData.name}
                description={selectedProviderData.description}
                target={target}
                onClose={() => setSelectedProvider(null)}
              />
            ) : null}
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}

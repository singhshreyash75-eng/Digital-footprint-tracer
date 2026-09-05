type InvestigationHeroProps = {
  running: boolean;
};

export default function InvestigationHero({
  running,
}: InvestigationHeroProps) {
  return (
    <section className={`hero ${running ? "hero--running" : ""}`}>
      <div className="section-label">
        {running ? "TRACE ACTIVE" : "DIGITAL INTELLIGENCE"}
      </div>

      <div className="hero-title-stack">
        <h1 className="hero-title hero-title--active">
          {running ? (
            <>
              Mapping the
              <span> footprint.</span>
            </>
          ) : (
            <>
              Trace the
              <span> public footprint.</span>
            </>
          )}
        </h1>
      </div>

      <div className="hero-copy-stack">
        <p className="hero-copy hero-copy--active mono">
          {running
            ? "> correlating publicly available identity signals..."
            : "> discover and correlate publicly available digital identities across the platforms that matter."}
        </p>
      </div>
    </section>
  );
}
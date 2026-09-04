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

      <h1>
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

      <p className="hero__description mono">
        {running
          ? "> correlating publicly available identity signals..."
          : "> discover and correlate publicly available digital identities across the platforms that matter."}
      </p>
    </section>
  );
}
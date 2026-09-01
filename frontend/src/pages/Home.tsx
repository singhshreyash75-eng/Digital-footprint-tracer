export default function Home() {
  return (
    <section className="home-page">
      <div className="ambient-orb ambient-orb-one" />
      <div className="ambient-orb ambient-orb-two" />

      <div className="hero-container">
        <div className="eyebrow">
          <span className="eyebrow-line" />
          DIGITAL INTELLIGENCE
        </div>

        <h1>
          Trace the
          <span> public footprint.</span>
        </h1>

        <p className="hero-description">
          Discover and correlate publicly available digital
          identities across the platforms that matter.
        </p>

        <div className="search-panel glass-surface">
          <div className="search-label">
            TARGET IDENTIFIER
          </div>

          <div className="search-row">
            <input
              type="text"
              placeholder="Enter a username..."
              aria-label="Target username"
            />

            <button className="search-button">
              <span>Investigate</span>
              <span className="arrow">→</span>
            </button>
          </div>

          <div className="search-hint">
            Username-based investigation • Public data only
          </div>
        </div>

        <div className="provider-strip">
          <span>CONNECTED SOURCES</span>

          <div className="provider-list">
            <span>GitHub</span>
            <span>Steam</span>
            <span>Twitch</span>
            <span>Stack Exchange</span>
          </div>
        </div>
      </div>
    </section>
  );
}
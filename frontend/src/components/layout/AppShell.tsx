import type { ReactNode } from "react";

type AppShellProps = {
  children: ReactNode;
};

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell">
      <div className="app-shell__ambient" aria-hidden="true">
        <div className="ambient-orb ambient-orb--one" />
        <div className="ambient-orb ambient-orb--two" />
        <div className="ambient-orb ambient-orb--three" />
      </div>

      <header className="topbar glass">
        <div className="topbar__brand">
          <div className="brand-mark">DFT</div>

          <div>
            <div className="topbar__title">Digital Footprint Tracer</div>

            <div className="topbar__subtitle">
              <span className="live-dot" />
              Intelligence surface
            </div>
          </div>
        </div>
      </header>

      <main>{children}</main>
    </div>
  );
}

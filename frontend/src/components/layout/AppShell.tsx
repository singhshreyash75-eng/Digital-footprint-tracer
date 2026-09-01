import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({
  children,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="topbar glass-surface">
        <div className="brand">
          <div className="brand-mark">DFT</div>

          <div>
            <div className="brand-name">
              Digital Footprint Tracer
            </div>

            <div className="brand-status">
              <span className="status-dot" />
              Intelligence surface
            </div>
          </div>
        </div>

        <div className="topbar-meta">
          <span>PUBLIC FOOTPRINT</span>
          <span className="topbar-divider" />
          <span>v1</span>
        </div>
      </header>

      <main className="app-content">
        {children}
      </main>
    </div>
  );
}
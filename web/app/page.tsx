import { ControlCards } from "@/components/control-cards";
import { Readiness } from "@/components/readiness";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { Workflow } from "@/components/workflow";

export default function Home() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="workspace">
        <Topbar />
        <main className="dashboard">
          <section className="hero">
            <div className="hero-copy">
              <p className="eyebrow hero-eyebrow">Research workspace</p>
              <h1>Evidence you can follow.<br />Judgment that stays human.</h1>
              <p className="hero-description">
                UW Analyzer turns external research into a controlled, traceable workflow for trade
                credit underwriting—without making the underwriting decision.
              </p>
            </div>
            <aside className="hero-note" aria-label="Current project phase">
              <span className="hero-note-number">00</span>
              <div>
                <small>Current project phase</small>
                <strong>Foundation &amp; governance</strong>
                <p>The workspace is ready for its first API-backed workflow.</p>
              </div>
            </aside>
          </section>

          <div className="dashboard-grid">
            <div className="dashboard-primary">
              <Workflow />
              <ControlCards />
            </div>
            <Readiness />
          </div>
        </main>
      </div>
    </div>
  );
}

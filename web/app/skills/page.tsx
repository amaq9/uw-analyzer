import { DocumentChartIcon } from "@/components/icons";
import { Sidebar } from "@/components/sidebar";
import { SkillMethod } from "@/components/skill-method";
import { SkillSafeguards } from "@/components/skill-safeguards";
import { Topbar } from "@/components/topbar";

export default function SkillsPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="skills" />
      <div className="workspace">
        <Topbar />
        <main className="dashboard skills-dashboard">
          <section className="skills-hero">
            <div className="skills-hero-icon"><DocumentChartIcon /></div>
            <div className="skills-hero-copy">
              <div className="skill-title-meta">
                <p className="eyebrow">Specialist skill · 01</p>
                <span className="method-badge">Configured methodology</span>
              </div>
              <h1>Financial Statement<br />Assessment</h1>
              <p>
                A structured, five-area review of financial statements for human-led trade credit
                underwriting. It highlights evidence, deterioration, and data gaps—never a decision.
              </p>
            </div>
            <div className="skill-purpose" aria-label="Skill purpose">
              <small>Purpose</small>
              <strong>Financial evidence review</strong>
              <span>Decision support only</span>
            </div>
          </section>

          <div className="skills-layout">
            <div className="skills-main-column">
              <SkillMethod />
              <section className="benchmark-notice" aria-labelledby="benchmark-title">
                <AlertIconProxy />
                <div>
                  <p className="eyebrow">Benchmark discipline</p>
                  <h2 id="benchmark-title">Indicative context is not verified peer evidence.</h2>
                  <p>
                    Any generic industry range must be labeled indicative and replaced with sourced,
                    dated peer data whenever it is used for a material conclusion.
                  </p>
                </div>
              </section>
            </div>
            <SkillSafeguards />
          </div>
        </main>
      </div>
    </div>
  );
}

function AlertIconProxy() {
  return (
    <span className="benchmark-mark" aria-hidden="true">
      <span>i</span>
    </span>
  );
}

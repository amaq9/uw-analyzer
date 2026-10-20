import type { Metadata } from "next";
import { DocumentChartIcon } from "@/components/icons";
import { Sidebar } from "@/components/sidebar";
import { SkillMethod } from "@/components/skill-method";
import { SkillPerspectives } from "@/components/skill-perspectives";
import { SkillSafeguards } from "@/components/skill-safeguards";
import { Topbar } from "@/components/topbar";

export const metadata: Metadata = { title: "Skills" };

export default function SkillsPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="skills" />
      <div className="workspace">
        <Topbar />
        <main className="dashboard skills-dashboard" id="main-content">
          <section className="skills-hero">
            <div className="skills-hero-icon"><DocumentChartIcon /></div>
            <div className="skills-hero-copy">
              <div className="skill-title-meta">
                <p className="eyebrow">Specialist skill · installed</p>
                <span className="method-badge">Enhanced · with published ratings</span>
              </div>
              <h1>Financial Statement<br />Assessment, Enhanced</h1>
              <p>
                The credit analyst&apos;s method behind every UW Analyzer recommendation: a JP Morgan-style review of five
                financial dimensions, read together with the annual report&apos;s notes and auditor and the published
                ratings of Moody&apos;s, S&amp;P and Fitch. It shows the evidence, what is deteriorating and what is
                missing. The underwriter makes the decision.
              </p>
            </div>
            <div className="skill-purpose" aria-label="Skill purpose">
              <small>Purpose</small>
              <strong>Credit analysis for trade credit</strong>
              <span>Recommendation only. The underwriter decides.</span>
            </div>
          </section>

          <div className="skills-layout">
            <div className="skills-main-column">
              <SkillMethod />
              <SkillPerspectives />
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

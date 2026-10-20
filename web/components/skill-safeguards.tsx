import Link from "next/link";

import { AlertIcon, ArrowIcon, CheckIcon } from "@/components/icons";

const requirements = [
  "A case with its legal entity confirmed",
  "Financial statements: fetched from SEC EDGAR for U.S. filers, or uploaded",
  "Current and prior-year figures where they are disclosed",
  "Published agency ratings recorded on the case, with their source",
];

const boundaries = [
  "A recommendation for the underwriter, never a decision: a named person decides",
  "Missing figures stay not disclosed, never estimated",
  "Every figure keeps its source and its inputs",
  "Agency ratings are shown for information and never change the amount",
  "Unsourced benchmarks stay indicative only",
];

export function SkillSafeguards() {
  return (
    <aside className="skill-side-column">
      <section className="panel integration-card" aria-labelledby="integration-title">
        <div className="integration-status-row is-live">
          <span className="connection-dot" />
          <span>In use</span>
        </div>
        <h2 id="integration-title">Runs on every<br />UW Analyzer analysis.</h2>
        <p>
          Open a case, go to the UW Analyzer recommendation tab and ask for the case to be analysed. Step 1 shows this
          skill&apos;s full analysis; Step 2 turns it into a recommendation under the approved policy; Step 3 is your decision.
        </p>
        <Link className="run-skill-button is-live" href="/cases">
          Open cases
          <ArrowIcon />
        </Link>
        <small>Skill: financial-statement-assessment-enhanced · analyzer v2 · recommendation policy v1.1</small>
      </section>

      <section className="panel skill-checklist" aria-labelledby="requirements-title">
        <div className="checklist-heading">
          <CheckIcon />
          <h2 id="requirements-title">Inputs the analysis needs</h2>
        </div>
        <ul>
          {requirements.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>

      <section className="panel skill-checklist boundary-list" aria-labelledby="boundaries-title">
        <div className="checklist-heading">
          <AlertIcon />
          <h2 id="boundaries-title">Non-negotiable boundaries</h2>
        </div>
        <ul>
          {boundaries.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>
    </aside>
  );
}

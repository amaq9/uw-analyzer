import { AlertIcon, CheckIcon, LockIcon } from "@/components/icons";

const requirements = [
  "Financial statement and reporting period",
  "Currency and presentation units",
  "Audited, reviewed, or management-account status",
  "Current and prior-period figures where disclosed",
];

const boundaries = [
  "No approval, decline, rating, or credit-limit output",
  "Missing figures remain not disclosed—not estimated",
  "Every calculated ratio retains its inputs",
  "Unsourced benchmarks remain indicative only",
];

export function SkillSafeguards() {
  return (
    <aside className="skill-side-column">
      <section className="panel integration-card" aria-labelledby="integration-title">
        <div className="integration-status-row">
          <span className="connection-dot" />
          <span>Backend connection required</span>
        </div>
        <h2 id="integration-title">Method ready.<br />Execution intentionally paused.</h2>
        <p>
          The skill is configured locally, but it is not yet present in the published API contract.
          No document or figure will be submitted until that interface is approved.
        </p>
        <button className="run-skill-button" type="button" disabled>
          <LockIcon />
          Run assessment
        </button>
        <small>Waiting for a versioned backend contract from Claude Code.</small>
      </section>

      <section className="panel skill-checklist" aria-labelledby="requirements-title">
        <div className="checklist-heading">
          <CheckIcon />
          <h2 id="requirements-title">Inputs the review needs</h2>
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

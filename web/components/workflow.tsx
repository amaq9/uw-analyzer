import { ArrowIcon, CheckIcon, LockIcon } from "@/components/icons";

const stages = [
  {
    number: "01",
    label: "Case intake",
    detail: "Capture the buyer and business context.",
  },
  {
    number: "02",
    label: "Entity resolution",
    detail: "Resolve the exact legal entity before research.",
    gate: true,
  },
  {
    number: "03",
    label: "Controlled research",
    detail: "Use only declared, accessible sources.",
  },
  {
    number: "04",
    label: "Evidence review",
    detail: "Verify claims and surface conflicts.",
  },
  {
    number: "05",
    label: "Human review",
    detail: "Hand an auditable report to the underwriter.",
  },
];

export function Workflow() {
  return (
    <section className="panel workflow-panel" aria-labelledby="workflow-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Core workflow</p>
          <h2 id="workflow-title">From intake to evidence, with no hidden leap</h2>
        </div>
        <span className="phase-tag">5 controlled stages</span>
      </div>
      <ol className="workflow-list">
        {stages.map((stage, index) => (
          <li key={stage.number} className={stage.gate ? "workflow-step gate" : "workflow-step"}>
            <div className="step-number">{stage.gate ? <LockIcon /> : stage.number}</div>
            <div className="step-copy">
              <div className="step-title-row">
                <h3>{stage.label}</h3>
                {stage.gate && <span className="required-badge">Required gate</span>}
              </div>
              <p>{stage.detail}</p>
            </div>
            {index < stages.length - 1 && <ArrowIcon className="workflow-arrow" />}
          </li>
        ))}
      </ol>
      <div className="workflow-rule">
        <CheckIcon />
        <p>
          If more than one legal entity is plausible, substantive research stops until a human resolves
          the ambiguity.
        </p>
      </div>
    </section>
  );
}

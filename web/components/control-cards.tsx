import { LockIcon, ResearchIcon, ShieldIcon } from "@/components/icons";

const controls = [
  {
    icon: LockIcon,
    kicker: "Human authority",
    title: "The system informs. The underwriter decides.",
    body: "No approval, decline, rating, or credit limit is produced by the platform.",
    tone: "navy",
  },
  {
    icon: ResearchIcon,
    kicker: "Evidence integrity",
    title: "Access and verification remain separate.",
    body: "Opening a source never automatically verifies every claim it contains.",
    tone: "teal",
  },
  {
    icon: ShieldIcon,
    kicker: "Traceability",
    title: "Every material claim keeps its evidence trail.",
    body: "Sources, dates, access records, and run versions remain inspectable.",
    tone: "sand",
  },
];

export function ControlCards() {
  return (
    <section aria-labelledby="controls-title">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Built-in safeguards</p>
          <h2 id="controls-title">Designed around defensible research</h2>
        </div>
      </div>
      <div className="control-grid">
        {controls.map(({ icon: ControlIcon, kicker, title, body, tone }) => (
          <article className={`control-card ${tone}`} key={kicker}>
            <div className="control-icon">
              <ControlIcon />
            </div>
            <p className="control-kicker">{kicker}</p>
            <h3>{title}</h3>
            <p>{body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

import { CheckIcon } from "@/components/icons";

const items = [
  {
    title: "Workspace foundation",
    detail: "Responsive shell, navigation, and accessible visual language",
    status: "Ready",
    ready: true,
  },
  {
    title: "Enterprise identity",
    detail: "Backend authentication skeleton available; UI integration follows the API contract",
    status: "In progress",
  },
  {
    title: "Case workflows",
    detail: "Intake and entity resolution begin in Phase 1",
    status: "Planned",
  },
];

export function Readiness() {
  return (
    <section className="panel readiness-panel" aria-labelledby="readiness-title">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Foundation readiness</p>
          <h2 id="readiness-title">What is connected today</h2>
        </div>
      </div>
      <ul className="readiness-list">
        {items.map((item) => (
          <li key={item.title}>
            <span className={item.ready ? "readiness-icon ready" : "readiness-icon"}>
              {item.ready ? <CheckIcon /> : <span />}
            </span>
            <span className="readiness-copy">
              <strong>{item.title}</strong>
              <small>{item.detail}</small>
            </span>
            <span className={item.ready ? "status-label ready" : "status-label"}>{item.status}</span>
          </li>
        ))}
      </ul>
      <div className="empty-activity">
        <span className="empty-glyph" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <div>
          <strong>No case activity yet</strong>
          <p>Live activity will appear after the first case workflow is connected.</p>
        </div>
      </div>
    </section>
  );
}

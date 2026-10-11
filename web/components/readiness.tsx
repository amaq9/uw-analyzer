import Link from "next/link";

import { CheckIcon } from "@/components/icons";

const items = [
  {
    title: "Cases and entity resolution",
    detail: "Intake, candidate entities, the ambiguity stop, uploads and the audit trail",
    status: "Ready",
    ready: true,
  },
  {
    title: "Research from public sources",
    detail: "SEC EDGAR, the Global LEI register, OFAC sanctions list and World Bank data; news is leads only",
    status: "Ready",
    ready: true,
  },
  {
    title: "Analysis and draft recommendation",
    detail: "Five-area financial review of SEC data or your own confirmed statements, then a draft for you",
    status: "Ready",
    ready: true,
  },
  {
    title: "Review, report and your decision",
    detail: "Human review items, an immutable versioned report, and your recorded decision",
    status: "Ready",
    ready: true,
  },
  {
    title: "Enterprise identity",
    detail: "Local test sign-in only in this test product",
    status: "Test only",
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
          <strong>Start with a case</strong>
          <p>
            Open <Link href="/cases">Cases</Link>, create one, choose the legal entity, then research and analyse it.
          </p>
        </div>
      </div>
    </section>
  );
}

import type { components } from "@/lib/api/schema";

export type ExecutiveBriefData = components["schemas"]["ExecutiveBrief"];

/** The summary for the person who decides: the recommendation, the reasons with their numbers, and what to settle first. */
/** The server writes every amount in its final form (for example "USD 5.00m"), so the text is shown as written. */
export function ExecutiveBriefCard({ brief }: Readonly<{ brief: ExecutiveBriefData; currency?: string | null }>) {
  const t = (text: string) => text;
  return (
    <section aria-label="Executive summary for the decision-maker" className="ws-card eb">
      <p className="eyebrow">Executive summary for the decision-maker</p>
      <p className="eb-headline">{t(brief.headline)}</p>
      <dl className="eb-sections">
        {brief.sections.map((section) => (
          <div key={section.heading}>
            <dt>{section.heading}</dt>
            <dd>{t(section.text)}</dd>
          </div>
        ))}
      </dl>
      {(brief.points_to_settle ?? []).length > 0 && (
        <div className="eb-points">
          <h3>Points to settle first</h3>
          <ol className="ws-bullets">
            {(brief.points_to_settle ?? []).map((point, index) => (
              <li key={`${index}-${point}`}>{t(point)}</li>
            ))}
          </ol>
        </div>
      )}
      <p className="ws-muted">
        Built from the whole analysis, so every sentence can be traced to Step 1. It is a recommendation only: your recorded
        decision is the decision.
      </p>
    </section>
  );
}

import type { ComponentType, SVGProps } from "react";

import {
  AlertIcon,
  AuditIcon,
  CasesIcon,
  DocumentChartIcon,
  ReportsIcon,
  ShieldIcon,
} from "@/components/icons";

type Perspective = {
  title: string;
  detail: string;
  checks: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
};

/** What the enhanced skill adds to the five dimensions, as the analysis shows it in Step 1 of a case. */
const perspectives: Perspective[] = [
  {
    title: "Published credit ratings",
    detail: "Each agency's grade, outlook and last action, with the agency's own stated reason and where it was reported.",
    checks: "Moody's · S&P · Fitch · downgrades and negative outlooks · information only, never changes the amount",
    icon: ReportsIcon,
  },
  {
    title: "Notes and auditor's report",
    detail: "Reads the printed annual report and quotes it, so what the figures leave out is not missed.",
    checks: "Audit opinion · going concern · covenants · credit facilities · customer concentration · internal control",
    icon: AuditIcon,
  },
  {
    title: "Cash conversion cycle",
    detail: "How long cash is tied up between paying suppliers and collecting from customers, against the year before.",
    checks: "Days sales outstanding · days inventory · days payables · the movement that drives it",
    icon: CasesIcon,
  },
  {
    title: "Warning signs",
    detail: "A fixed checklist of credit red flags, each shown as triggered, clear or not assessable, with its numbers.",
    checks: "Cash below profit · payouts above free cash flow · receivables outpacing sales · rising leverage",
    icon: AlertIcon,
  },
  {
    title: "If sales fall",
    detail: "What happens to operating profit and cash if revenue drops, and the fall at which profit reaches zero.",
    checks: "10% and 20% revenue falls · break-even point · illustration, not a forecast",
    icon: DocumentChartIcon,
  },
  {
    title: "Screening and context",
    detail: "Checks around the company that the financial statements cannot show.",
    checks: "Sanctions name search · legal entity register · country economy · news leads",
    icon: ShieldIcon,
  },
];

export function SkillPerspectives() {
  return (
    <section className="skill-method" aria-labelledby="skill-perspectives-title">
      <div className="section-heading skill-section-heading">
        <div>
          <p className="eyebrow">Enhanced skill</p>
          <h2 id="skill-perspectives-title">Beyond the ratios</h2>
        </div>
        <span className="phase-tag">Ratings, notes and risk</span>
      </div>
      <ul className="method-grid perspective-grid">
        {perspectives.map(({ title, detail, checks, icon: PerspectiveIcon }) => (
          <li key={title} className="method-card">
            <div className="method-card-top">
              <span className="method-icon"><PerspectiveIcon /></span>
            </div>
            <h3>{title}</h3>
            <p>{detail}</p>
            <small>{checks}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}

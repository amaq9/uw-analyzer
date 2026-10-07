import type { ComponentType, SVGProps } from "react";

import {
  CasesIcon,
  DocumentChartIcon,
  EvidenceIcon,
  ReportsIcon,
  ResearchIcon,
} from "@/components/icons";

type MethodItem = {
  number: string;
  title: string;
  detail: string;
  checks: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
};

const method: MethodItem[] = [
  {
    number: "01",
    title: "Balance sheet strength",
    detail: "Assess the equity buffer and the quality of the asset base.",
    checks: "Assets · liabilities · equity · goodwill · disclosed ratings",
    icon: CasesIcon,
  },
  {
    number: "02",
    title: "Liquidity",
    detail: "Test short-term obligations against genuinely available resources.",
    checks: "Current · quick · cash ratios · working capital · maturities",
    icon: ResearchIcon,
  },
  {
    number: "03",
    title: "Gearing",
    detail: "Separate gross debt, leases, and net debt from headline leverage.",
    checks: "Debt · net debt · leases · EBITDA · interest cover",
    icon: ReportsIcon,
  },
  {
    number: "04",
    title: "Receivables aging",
    detail: "Show collection pressure and say plainly when aging is not disclosed.",
    checks: "Receivables · DSO · allowance · cash absorbed · aging gaps",
    icon: EvidenceIcon,
  },
  {
    number: "05",
    title: "Cash flow generation",
    detail: "Follow cash through operations, investment, and distributions.",
    checks: "OCF · free cash flow · dividends · buybacks · change in cash",
    icon: DocumentChartIcon,
  },
];

export function SkillMethod() {
  return (
    <section className="skill-method" aria-labelledby="skill-method-title">
      <div className="section-heading skill-section-heading">
        <div>
          <p className="eyebrow">Required review sequence</p>
          <h2 id="skill-method-title">Five areas, always in this order</h2>
        </div>
        <span className="phase-tag">Financial evidence</span>
      </div>
      <ol className="method-grid">
        {method.map(({ number, title, detail, checks, icon: MethodIcon }) => (
          <li key={number} className="method-card">
            <div className="method-card-top">
              <span className="method-number">{number}</span>
              <span className="method-icon"><MethodIcon /></span>
            </div>
            <h3>{title}</h3>
            <p>{detail}</p>
            <small>{checks}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}

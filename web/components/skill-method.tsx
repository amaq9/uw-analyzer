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
    title: "Liquidity",
    detail: "Test short-term obligations against genuinely available resources.",
    checks: "Current · quick · cash ratios · working capital · cash from operations over current liabilities",
    icon: ResearchIcon,
  },
  {
    number: "02",
    title: "Profitability",
    detail: "Check that profits are real, sustainable and turning into cash.",
    checks: "Gross · operating · EBITDA · net margin · return on assets and equity · trend",
    icon: CasesIcon,
  },
  {
    number: "03",
    title: "Leverage",
    detail: "Separate gross debt, leases and net debt from headline leverage.",
    checks: "Debt to equity · equity share of assets · interest cover · net debt to EBITDA",
    icon: ReportsIcon,
  },
  {
    number: "04",
    title: "Cash flow",
    detail: "Follow cash through operations, investment and distributions.",
    checks: "Cash from operations · free cash flow · conversion of profit · capital spending",
    icon: DocumentChartIcon,
  },
  {
    number: "05",
    title: "Efficiency and sector",
    detail: "Show how hard the assets work, and say plainly that no peer data is connected.",
    checks: "Asset turnover · receivables days · inventory turnover · concentration and market share not assessed",
    icon: EvidenceIcon,
  },
];

export function SkillMethod() {
  return (
    <section className="skill-method" aria-labelledby="skill-method-title">
      <div className="section-heading skill-section-heading">
        <div>
          <p className="eyebrow">Required review sequence</p>
          <h2 id="skill-method-title">Five dimensions, always in this order</h2>
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

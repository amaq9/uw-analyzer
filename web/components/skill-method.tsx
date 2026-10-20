import type { ComponentType, SVGProps } from "react";

import { DocumentChartIcon, GearIcon, ReportsIcon, ResearchIcon } from "@/components/icons";

type Dimension = {
  number: string;
  title: string;
  question: string;
  includes: string[];
  icon: ComponentType<SVGProps<SVGSVGElement>>;
};

/** The five dimensions in the order the analysis always follows. "Includes" lists measures Step 1 actually shows. */
const dimensions: Dimension[] = [
  {
    number: "01",
    title: "Profitability",
    question: "Can the business generate sustainable profit and convert it into cash?",
    includes: ["Gross margin", "Operating margin", "EBITDA", "Net margin", "ROA", "ROE"],
    icon: ReportsIcon,
  },
  {
    number: "02",
    title: "Liquidity",
    question: "Can the business meet short-term obligations using genuinely available resources?",
    includes: ["Current ratio", "Quick ratio", "Cash ratio", "Working capital"],
    icon: ResearchIcon,
  },
  {
    number: "03",
    title: "Balance sheet and leverage",
    question: "Separate gross debt, leases and net debt from headline leverage.",
    includes: ["Debt-to-equity", "Equity share", "Interest cover", "Net debt-to-EBITDA"],
    icon: ReportsIcon,
  },
  {
    number: "04",
    title: "Cash flow",
    question: "Follow cash through operations, investment and distributions.",
    includes: ["Cash from operations", "Free cash flow", "Capital spending", "Cash conversion cycle"],
    icon: DocumentChartIcon,
  },
  {
    number: "05",
    title: "Efficiency and sector",
    question: "Show how hard the assets work. Peer comparison needs sourced peer data, which is not connected yet.",
    includes: ["Asset turnover", "Receivable days", "Inventory turnover", "Sector context"],
    icon: GearIcon,
  },
];

export function SkillMethod() {
  return (
    <section className="skill-section" aria-labelledby="skill-method-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Required financial review</p>
          <h2 id="skill-method-title">Five dimensions, reviewed in order</h2>
        </div>
        <span className="phase-tag">5 required dimensions</span>
      </div>
      <ol className="track dimension-track">
        {dimensions.map(({ number, title, question, includes, icon: DimensionIcon }) => (
          <li key={number} className="track-stage">
            <span className="track-node" aria-hidden="true">
              {number}
            </span>
            <div className="track-card">
              <span className="icon-tile">
                <DimensionIcon />
              </span>
              <h3>{title}</h3>
              <p>{question}</p>
              <div className="track-includes">
                <span>Review includes</span>
                <p>{includes.join(" · ")}</p>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

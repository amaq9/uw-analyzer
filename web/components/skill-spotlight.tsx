import Link from "next/link";

import { ArrowIcon, DocumentChartIcon } from "@/components/icons";

export function SkillSpotlight() {
  return (
    <section className="skill-spotlight" aria-labelledby="skill-spotlight-title">
      <div className="skill-spotlight-icon">
        <DocumentChartIcon />
      </div>
      <div className="skill-spotlight-copy">
        <div className="skill-spotlight-meta">
          <span>New specialist skill</span>
          <span className="method-badge">Method ready</span>
        </div>
        <h2 id="skill-spotlight-title">Financial Statement Assessment</h2>
        <p>
          A five-dimension financial review built for trade credit evidence: profitability, liquidity,
          balance sheet and leverage, cash flow, and efficiency and sector.
        </p>
      </div>
      <Link className="skill-spotlight-link" href="/skills">
        Explore skill
        <ArrowIcon />
      </Link>
    </section>
  );
}

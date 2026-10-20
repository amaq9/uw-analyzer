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
          <span>Specialist skill</span>
          <span className="method-badge">Enhanced · in use</span>
        </div>
        <h2 id="skill-spotlight-title">Financial Statement Assessment, Enhanced</h2>
        <p>
          Five financial dimensions (profitability, liquidity, balance sheet and leverage, cash flow, efficiency and
          sector), read with the annual report&apos;s notes and auditor and the published agency ratings.
        </p>
      </div>
      <Link className="skill-spotlight-link" href="/skills">
        Explore skill
        <ArrowIcon />
      </Link>
    </section>
  );
}

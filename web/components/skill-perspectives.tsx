import type { ComponentType, SVGProps } from "react";

import {
  AlertIcon,
  DocumentChartIcon,
  EvidenceIcon,
  FolderIcon,
  GearIcon,
  ReportsIcon,
  ShieldIcon,
  TrendIcon,
} from "@/components/icons";

type Item = { title: string; detail: string; icon: ComponentType<SVGProps<SVGSVGElement>> };
type Group = { key: string; title: string; icon: ComponentType<SVGProps<SVGSVGElement>>; items: Item[] };

/** What the enhanced skill adds to the five dimensions, grouped as Step 1 of a case shows it. */
const groups: Group[] = [
  {
    key: "corroboration",
    title: "External corroboration",
    icon: EvidenceIcon,
    items: [
      {
        title: "Published third-party credit ratings",
        detail: "Show the agency, rating date, outlook and linked source.",
        icon: ReportsIcon,
      },
      {
        title: "Notes and auditor's report",
        detail: "Read the printed annual report and quoted notes for hidden figures and risk context.",
        icon: EvidenceIcon,
      },
    ],
  },
  {
    key: "diagnostics",
    title: "Operating diagnostics",
    icon: GearIcon,
    items: [
      {
        title: "Cash conversion cycle",
        detail: "Show how long cash is tied up between paying suppliers and collecting from customers.",
        icon: FolderIcon,
      },
      {
        title: "Warning signs",
        detail: "Display each triggered red flag with its figures, source and limitations.",
        icon: AlertIcon,
      },
    ],
  },
  {
    key: "stress",
    title: "Stress testing and context",
    icon: TrendIcon,
    items: [
      {
        title: "Revenue decline scenario",
        detail: "Show what happens to operating profit and cash under clearly stated downside assumptions.",
        icon: DocumentChartIcon,
      },
      {
        title: "Screening and reporting context",
        detail: "Check whether sanctions, legal structure or reporting context limit interpretation.",
        icon: ShieldIcon,
      },
    ],
  },
];

export function SkillPerspectives() {
  return (
    <section className="skill-section" aria-labelledby="skill-perspectives-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Enhanced review</p>
          <h2 id="skill-perspectives-title">Corroboration, context and stress testing</h2>
        </div>
        <span className="phase-tag">Beyond the ratios</span>
      </div>
      <div className="review-groups">
        {groups.map(({ key, title, icon: GroupIcon, items }) => (
          <section key={key} className={`review-group is-${key}`} aria-labelledby={`review-group-${key}`}>
            <h3 className="review-group-head" id={`review-group-${key}`}>
              <GroupIcon />
              {title}
            </h3>
            <ul>
              {items.map(({ title: itemTitle, detail, icon: ItemIcon }) => (
                <li key={itemTitle} className="review-item">
                  <span className="icon-tile">
                    <ItemIcon />
                  </span>
                  <div>
                    <h4>{itemTitle}</h4>
                    <p>{detail}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </section>
  );
}

import Link from "next/link";

import { Brand } from "@/components/brand";
import {
  AuditIcon,
  CasesIcon,
  EvidenceIcon,
  OverviewIcon,
  ReportsIcon,
  ResearchIcon,
  ShieldIcon,
  SkillsIcon,
} from "@/components/icons";

const workspaceLinks = [
  { id: "overview", label: "Overview", icon: OverviewIcon, href: "/" },
  { id: "skills", label: "Skills", icon: SkillsIcon, href: "/skills", badge: "1" },
  { label: "Cases", icon: CasesIcon },
  { label: "Research queue", icon: ResearchIcon },
  { label: "Evidence", icon: EvidenceIcon },
  { label: "Reports", icon: ReportsIcon },
];

const governanceLinks = [
  { label: "Audit trail", icon: AuditIcon },
  { label: "Source access", icon: ShieldIcon },
];

type SidebarProps = {
  activePage?: "overview" | "skills";
};

export function Sidebar({ activePage = "overview" }: SidebarProps) {
  return (
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Primary navigation">
        <p className="nav-label">Workspace</p>
        <ul className="nav-list workspace-nav">
          {workspaceLinks.map((item) => {
            const LinkIcon = item.icon;
            const active = item.id === activePage;

            return (
              <li key={item.label}>
                {item.href ? (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={active ? "nav-item active" : "nav-item"}
                    href={item.href}
                  >
                    <LinkIcon className="nav-icon" />
                    {item.label}
                    {item.badge && <span className="nav-count">{item.badge}</span>}
                  </Link>
                ) : (
                  <span className="nav-item unavailable" title="Available in a later project phase">
                    <LinkIcon className="nav-icon" />
                    {item.label}
                    <span className="nav-soon">Soon</span>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        <p className="nav-label governance-label">Governance</p>
        <ul className="nav-list governance-nav">
          {governanceLinks.map(({ label, icon: LinkIcon }) => (
            <li key={label}>
              <span className="nav-item unavailable" title="Available in a later project phase">
                <LinkIcon className="nav-icon" />
                {label}
                <span className="nav-soon">Soon</span>
              </span>
            </li>
          ))}
        </ul>
      </nav>
      <div className="sidebar-note">
        <ShieldIcon />
        <div>
          <strong>Decision support only</strong>
          <span>The underwriter retains decision authority.</span>
        </div>
      </div>
    </aside>
  );
}

import Link from "next/link";

import { Brand } from "@/components/brand";
import {
  AuditIcon,
  CasesIcon,
  OverviewIcon,
  ReportsIcon,
  ShieldIcon,
  SkillsIcon,
} from "@/components/icons";

const workspaceLinks = [
  { id: "overview", label: "Overview", icon: OverviewIcon, href: "/" },
  { id: "skills", label: "Skills", icon: SkillsIcon, href: "/skills", badge: "1" },
  { id: "cases", label: "Cases", icon: CasesIcon, href: "/cases" },
  { id: "agreement", label: "Draft against decision", icon: ReportsIcon, href: "/agreement" },
];

const governanceLinks = [
  { id: "sources", label: "Source access", icon: ShieldIcon, href: "/sources" },
  { label: "Audit trail", icon: AuditIcon },
];

type SidebarProps = {
  activePage?: "agreement" | "cases" | "overview" | "skills" | "sources";
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
          {governanceLinks.map((item) => {
            const LinkIcon = item.icon;
            const active = "id" in item && item.id === activePage;

            return (
              <li key={item.label}>
                {"href" in item && item.href ? (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={active ? "nav-item active" : "nav-item"}
                    href={item.href}
                  >
                    <LinkIcon className="nav-icon" />
                    {item.label}
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

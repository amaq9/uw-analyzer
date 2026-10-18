"use client";

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
import { useSession } from "@/components/session-provider";

const workspaceLinks = [
  { id: "overview", label: "Overview", icon: OverviewIcon, href: "/" },
  { id: "skills", label: "Skills", icon: SkillsIcon, href: "/skills", badge: "1" },
  { id: "cases", label: "Cases", icon: CasesIcon, href: "/cases", permissions: ["case:read"] },
  {
    id: "recommendations",
    label: "UW Analyzer recommendations",
    icon: ReportsIcon,
    href: "/recommendations",
    permissions: ["case:read"],
  },
  {
    id: "agreement",
    label: "UW Analyzer versus actual decision",
    icon: ReportsIcon,
    href: "/agreement",
    permissions: ["case:read"],
  },
];

const governanceLinks = [
  {
    id: "sources",
    label: "Source access",
    icon: ShieldIcon,
    href: "/sources",
    permissions: ["admin:manage", "case:read", "research:run"],
  },
  { id: "audit", label: "Audit trail", icon: AuditIcon, href: "/audit", permissions: ["audit:read"] },
];

type SidebarProps = {
  activePage?: "agreement" | "audit" | "cases" | "overview" | "recommendations" | "skills" | "sources";
};

export function Sidebar({ activePage = "overview" }: SidebarProps) {
  const { session } = useSession();
  const visibleWorkspaceLinks = workspaceLinks.filter(
    (item) => !("permissions" in item) || item.permissions?.some((permission) => session?.user.permissions.includes(permission)),
  );
  const visibleGovernanceLinks = governanceLinks.filter((item) =>
    item.permissions.some((permission) => session?.user.permissions.includes(permission)),
  );

  return (
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Primary navigation">
        <p className="nav-label">Workspace</p>
        <ul className="nav-list workspace-nav">
          {visibleWorkspaceLinks.map((item) => {
            const LinkIcon = item.icon;
            const active = item.id === activePage;

            return (
              <li key={item.label}>
                <Link
                  aria-current={active ? "page" : undefined}
                  className={active ? "nav-item active" : "nav-item"}
                  href={item.href}
                >
                  <LinkIcon className="nav-icon" />
                  {item.label}
                  {"badge" in item && item.badge && <span className="nav-count">{item.badge}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
        <p className="nav-label governance-label">Governance</p>
        <ul className="nav-list governance-nav">
          {visibleGovernanceLinks.map((item) => {
            const LinkIcon = item.icon;
            const active = "id" in item && item.id === activePage;

            return (
              <li key={item.label}>
                <Link
                  aria-current={active ? "page" : undefined}
                  className={active ? "nav-item active" : "nav-item"}
                  href={item.href}
                >
                  <LinkIcon className="nav-icon" />
                  {item.label}
                </Link>
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

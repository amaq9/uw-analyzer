"use client";

import Link from "next/link";
import type { ComponentType, SVGProps } from "react";

import { Brand } from "@/components/brand";
import {
  CasesIcon,
  DocumentCheckIcon,
  DocumentSearchIcon,
  HistoryIcon,
  OverviewIcon,
  ShieldIcon,
  SkillsIcon,
} from "@/components/icons";
import { useSession } from "@/components/session-provider";

type PageId = "agreement" | "audit" | "cases" | "overview" | "recommendations" | "skills" | "sources";

type NavLink = {
  id: PageId;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  href: string;
  /** Shown when the user has any of these permissions. No list: shown to everyone. */
  permissions?: string[];
};

type NavSection = { label: string; links: NavLink[] };

const sections: NavSection[] = [
  {
    label: "Workspace",
    links: [
      { id: "overview", label: "Overview", icon: OverviewIcon, href: "/" },
      { id: "cases", label: "Cases", icon: CasesIcon, href: "/cases", permissions: ["case:read"] },
      { id: "skills", label: "Skills", icon: SkillsIcon, href: "/skills" },
    ],
  },
  {
    label: "Analysis",
    links: [
      {
        id: "recommendations",
        label: "UW Analyzer recommendation",
        icon: DocumentSearchIcon,
        href: "/recommendations",
        permissions: ["case:read"],
      },
      { id: "agreement", label: "Decision Outcome", icon: DocumentCheckIcon, href: "/agreement", permissions: ["case:read"] },
    ],
  },
  {
    label: "Governance",
    links: [
      {
        id: "sources",
        label: "Source access",
        icon: ShieldIcon,
        href: "/sources",
        permissions: ["admin:manage", "case:read", "research:run"],
      },
      { id: "audit", label: "Audit history", icon: HistoryIcon, href: "/audit", permissions: ["audit:read"] },
    ],
  },
];

type SidebarProps = {
  activePage?: PageId;
};

export function Sidebar({ activePage = "overview" }: SidebarProps) {
  const { session } = useSession();
  const granted = session?.user.permissions ?? [];
  // A section the user can see nothing in is left out, heading and all.
  const visible = sections
    .map((section) => ({
      ...section,
      links: section.links.filter((link) => !link.permissions || link.permissions.some((p) => granted.includes(p))),
    }))
    .filter((section) => section.links.length > 0);

  return (
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Primary navigation">
        {visible.map((section) => (
          <div className="nav-section" key={section.label}>
            <p className="nav-label" id={`nav-${section.label.toLowerCase()}`}>
              {section.label}
            </p>
            <ul aria-labelledby={`nav-${section.label.toLowerCase()}`} className="nav-list">
              {section.links.map((item) => {
                const LinkIcon = item.icon;
                const active = item.id === activePage;
                return (
                  <li key={item.id}>
                    <Link
                      aria-current={active ? "page" : undefined}
                      className={active ? "nav-item active" : "nav-item"}
                      href={item.href}
                    >
                      <LinkIcon className="nav-icon" />
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
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

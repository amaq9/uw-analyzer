import { Brand } from "@/components/brand";
import {
  AuditIcon,
  CasesIcon,
  EvidenceIcon,
  OverviewIcon,
  ReportsIcon,
  ResearchIcon,
  ShieldIcon,
} from "@/components/icons";

const workspaceLinks = [
  { label: "Overview", icon: OverviewIcon, active: true },
  { label: "Cases", icon: CasesIcon },
  { label: "Research queue", icon: ResearchIcon },
  { label: "Evidence", icon: EvidenceIcon },
  { label: "Reports", icon: ReportsIcon },
];

const governanceLinks = [
  { label: "Audit trail", icon: AuditIcon },
  { label: "Source access", icon: ShieldIcon },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Primary navigation">
        <p className="nav-label">Workspace</p>
        <ul className="nav-list">
          {workspaceLinks.map(({ label, icon: LinkIcon, active }) => (
            <li key={label}>
              <span
                aria-current={active ? "page" : undefined}
                className={active ? "nav-item active" : "nav-item unavailable"}
                title={active ? undefined : "Available in a later project phase"}
              >
                <LinkIcon className="nav-icon" />
                {label}
                {!active && <span className="nav-soon">Soon</span>}
              </span>
            </li>
          ))}
        </ul>
        <p className="nav-label governance-label">Governance</p>
        <ul className="nav-list">
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

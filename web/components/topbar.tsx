import Link from "next/link";

import { MenuIcon, ShieldIcon } from "@/components/icons";

export function Topbar() {
  return (
    <header className="topbar">
      <button aria-label="Open navigation" className="menu-button" disabled type="button">
        <MenuIcon />
      </button>
      <div className="environment-pill">
        <span className="environment-dot" />
        Development preview
      </div>
      <div className="topbar-actions">
        <div className="discipline-status">
          <ShieldIcon />
          <span>
            <small>Research control</small>
            <strong>Evidence discipline active</strong>
          </span>
        </div>
        <Link className="user-chip" href="/sign-in" aria-label="Open access screen">
          <span className="avatar">AU</span>
          <span className="user-copy">
            <strong>Authorized user</strong>
            <small>Workspace preview</small>
          </span>
        </Link>
      </div>
    </header>
  );
}

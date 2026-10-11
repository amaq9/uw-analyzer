"use client";

import Link from "next/link";

import { ShieldIcon } from "@/components/icons";
import { useSession } from "@/components/session-provider";

export function Topbar() {
  const { session, signOut } = useSession();
  const subject = session?.user.subject ?? "Authorized user";
  const initials = subject.slice(0, 2).toUpperCase();

  function handleSignOut() {
    signOut();
  }

  return (
    <header className="topbar">
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
          <span className="avatar">{initials}</span>
          <span className="user-copy">
            <strong>{subject}</strong>
            <small>{session ? "Local session" : "Workspace preview"}</small>
          </span>
        </Link>
        {session && (
          <button className="topbar-sign-out" onClick={handleSignOut} type="button">
            Sign out
          </button>
        )}
      </div>
    </header>
  );
}

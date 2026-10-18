import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import { SourcesAdmin } from "@/components/sources-admin";
import { Topbar } from "@/components/topbar";

export const metadata: Metadata = { title: "Source access" };

export default function SourcesPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="sources" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page" id="main-content">
          <SourcesAdmin />
        </main>
      </div>
    </div>
  );
}

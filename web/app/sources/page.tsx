import { Sidebar } from "@/components/sidebar";
import { SourcesAdmin } from "@/components/sources-admin";
import { Topbar } from "@/components/topbar";

export default function SourcesPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="sources" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page">
          <SourcesAdmin />
        </main>
      </div>
    </div>
  );
}

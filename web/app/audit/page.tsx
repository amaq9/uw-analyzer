import { AuditTrail } from "@/components/audit-trail";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export default function AuditPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="audit" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page" id="main-content">
          <AuditTrail />
        </main>
      </div>
    </div>
  );
}

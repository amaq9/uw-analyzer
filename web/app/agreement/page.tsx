import { AgreementView } from "@/components/agreement-view";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export default function AgreementPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="agreement" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page">
          <AgreementView />
        </main>
      </div>
    </div>
  );
}

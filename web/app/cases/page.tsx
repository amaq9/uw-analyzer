import { CaseList } from "@/components/case-list";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export default function CasesPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="cases" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page">
          <CaseList />
        </main>
      </div>
    </div>
  );
}

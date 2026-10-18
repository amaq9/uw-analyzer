import type { Metadata } from "next";
import { AgreementView } from "@/components/agreement-view";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export const metadata: Metadata = { title: "UW Analyzer versus actual decision" };

export default function AgreementPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="agreement" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page" id="main-content">
          <AgreementView />
        </main>
      </div>
    </div>
  );
}

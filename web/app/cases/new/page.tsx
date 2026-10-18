import type { Metadata } from "next";
import { CaseForm } from "@/components/case-form";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export const metadata: Metadata = { title: "New case" };

export default function NewCasePage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="cases" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page" id="main-content">
          <CaseForm mode="create" />
        </main>
      </div>
    </div>
  );
}

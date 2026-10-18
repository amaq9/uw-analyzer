import type { Metadata } from "next";
import { CaseForm } from "@/components/case-form";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

type EditCasePageProps = {
  params: Promise<{ caseId: string }>;
};

export const metadata: Metadata = { title: "Edit case" };

export default async function EditCasePage({ params }: EditCasePageProps) {
  const { caseId } = await params;
  return (
    <div className="app-shell">
      <Sidebar activePage="cases" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page" id="main-content">
          <CaseForm caseId={caseId} mode="edit" />
        </main>
      </div>
    </div>
  );
}

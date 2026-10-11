import { CaseForm } from "@/components/case-form";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

type EditCasePageProps = {
  params: Promise<{ caseId: string }>;
};

export default async function EditCasePage({ params }: EditCasePageProps) {
  const { caseId } = await params;
  return (
    <div className="app-shell">
      <Sidebar activePage="cases" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page">
          <CaseForm caseId={caseId} mode="edit" />
        </main>
      </div>
    </div>
  );
}

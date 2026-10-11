import { CaseWorkspace } from "@/components/case/workspace";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

type CasePageProps = {
  params: Promise<{ caseId: string }>;
};

export default async function CasePage({ params }: CasePageProps) {
  const { caseId } = await params;

  return (
    <div className="app-shell">
      <Sidebar activePage="cases" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page">
          <CaseWorkspace caseId={caseId} />
        </main>
      </div>
    </div>
  );
}

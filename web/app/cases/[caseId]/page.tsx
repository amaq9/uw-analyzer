import type { Metadata } from "next";
import { CaseWorkspace } from "@/components/case/workspace";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

type CasePageProps = {
  params: Promise<{ caseId: string }>;
};

export const metadata: Metadata = { title: "Case" };

export default async function CasePage({ params }: CasePageProps) {
  const { caseId } = await params;

  return (
    <div className="app-shell">
      <Sidebar activePage="cases" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page" id="main-content">
          <CaseWorkspace caseId={caseId} />
        </main>
      </div>
    </div>
  );
}

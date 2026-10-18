import type { Metadata } from "next";
import { DraftRecommendationView } from "@/components/draft-recommendation-view";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

type DraftRecommendationPageProps = {
  params: Promise<{ caseId: string; draftId: string }>;
};

export const metadata: Metadata = { title: "Draft recommendation" };

export default async function DraftRecommendationPage({ params }: DraftRecommendationPageProps) {
  const { caseId, draftId } = await params;

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="workspace">
        <Topbar />
        <main className="draft-page" id="main-content">
          <DraftRecommendationView caseId={caseId} draftId={draftId} />
        </main>
      </div>
    </div>
  );
}

import type { Metadata } from "next";
import { RecommendationsOverview } from "@/components/recommendations-overview";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export const metadata: Metadata = { title: "UW Analyzer recommendations" };

export default function RecommendationsPage() {
  return (
    <div className="app-shell">
      <Sidebar activePage="recommendations" />
      <div className="workspace">
        <Topbar />
        <main className="cases-page" id="main-content">
          <RecommendationsOverview />
        </main>
      </div>
    </div>
  );
}

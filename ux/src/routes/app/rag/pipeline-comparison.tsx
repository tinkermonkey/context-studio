import { createFileRoute } from "@tanstack/react-router";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar } from "@/components/layout/cs_sidebar";

export const Route = createFileRoute("/app/rag/pipeline-comparison")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar></CsSidebar>
      <CsMain>
        <CsMainTitle>Pipeline Comparison</CsMainTitle>
        <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-gray-600 dark:text-gray-400">
            Pipeline comparison tool - coming soon. This will allow you to compare
            the performance of different RAG pipeline configurations side-by-side.
          </p>
        </div>
      </CsMain>
    </>
  );
}

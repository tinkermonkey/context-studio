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
          <h2 className="mb-4 text-xl font-semibold text-gray-900 dark:text-white">
            Coming Soon
          </h2>
          <div className="mb-6 space-y-2 text-gray-600 dark:text-gray-400">
            <p className="font-medium">
              Pipeline comparison tool for evaluating different RAG
              configurations side-by-side.
            </p>
            <p>Planned features include:</p>
            <ul className="ml-6 list-disc space-y-1">
              <li>Side-by-side pipeline performance comparison</li>
              <li>Quality metrics and scoring visualization</li>
              <li>Response time and efficiency analysis</li>
              <li>Cost comparison across configurations</li>
              <li>Export comparison reports for documentation</li>
            </ul>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-500">
            Expected availability: Version 0.2.0 •{" "}
            <a
              href="https://github.com/your-org/context-studio/issues"
              className="text-blue-600 hover:underline dark:text-blue-400"
              target="_blank"
              rel="noopener noreferrer"
            >
              Track progress
            </a>
          </p>
        </div>
      </CsMain>
    </>
  );
}

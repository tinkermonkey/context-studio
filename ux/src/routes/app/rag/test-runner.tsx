import { createFileRoute } from "@tanstack/react-router";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar } from "@/components/layout/cs_sidebar";

export const Route = createFileRoute("/app/rag/test-runner")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar></CsSidebar>
      <CsMain>
        <CsMainTitle>Test Runner</CsMainTitle>
        <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <h2 className="mb-4 text-xl font-semibold text-gray-900 dark:text-white">
            Coming Soon
          </h2>
          <div className="mb-6 space-y-2 text-gray-600 dark:text-gray-400">
            <p className="font-medium">
              Pipeline test runner for executing and managing RAG pipeline tests at scale.
            </p>
            <p>Planned features include:</p>
            <ul className="ml-6 list-disc space-y-1">
              <li>Batch test execution for multiple queries</li>
              <li>Test suite management and organization</li>
              <li>Automated regression testing</li>
              <li>Performance benchmarking across test sets</li>
              <li>Test result history and trend analysis</li>
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

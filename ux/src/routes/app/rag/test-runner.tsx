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
          <p className="text-gray-600 dark:text-gray-400">
            Pipeline test runner - coming soon. This will provide a dedicated
            interface for running and managing pipeline tests at scale.
          </p>
        </div>
      </CsMain>
    </>
  );
}

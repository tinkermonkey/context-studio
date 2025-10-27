import { createFileRoute } from "@tanstack/react-router";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar } from "@/components/layout/cs_sidebar";

// TODO: Add access control/route guards before production deployment
// This is an admin/developer tool that should be protected

export const Route = createFileRoute("/app/monitoring/system-health")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar></CsSidebar>
      <CsMain>
        <CsMainTitle>System Health</CsMainTitle>
        <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <h2 className="mb-4 text-xl font-semibold text-gray-900 dark:text-white">
            Coming Soon
          </h2>
          <div className="mb-6 space-y-2 text-gray-600 dark:text-gray-400">
            <p className="font-medium">
              System health monitoring dashboard for tracking application stability and service status.
            </p>
            <p>Planned features include:</p>
            <ul className="ml-6 list-disc space-y-1">
              <li>Database connection status and health checks</li>
              <li>Event processor operational status</li>
              <li>Service uptime and availability metrics</li>
              <li>System resource utilization (CPU, memory, disk)</li>
              <li>Error rate tracking and alerting</li>
            </ul>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-500">
            Expected availability: Version 0.3.0 •{" "}
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

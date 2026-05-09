import { createFileRoute } from "@tanstack/react-router";
import { CurrentDatasetCard } from "@/components/datasets/current_dataset_card";
import { DatasetHistory } from "@/components/datasets/dataset_history";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { DatasetsTable } from "@/components/datasets/datasets_table";

export const Route = createFileRoute("/app/datasets")({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Dataset History</CsSidebarTitle>
        <div className="mt-4">
          <DatasetHistory days={7} maxEntries={8} />
        </div>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>Dataset Management</CsMainTitle>

        <div className="space-y-6">
          {/* Current Active Dataset */}
          <div>
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Current Dataset
            </h2>
          </div>
          <CurrentDatasetCard />
        </div>
        <CsMainTitle className="mt-12">Dataset Inventory</CsMainTitle>
        <DatasetsTable className="mt-8" />
      </CsMain>
    </>
  );
}

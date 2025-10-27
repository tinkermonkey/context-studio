import { createFileRoute, Link } from "@tanstack/react-router";
import { Alert, Breadcrumb } from "flowbite-react";
import {  Home } from "lucide-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import type { PipelineType } from "@/api/services/pipelineFlavors";
import { PipelineTypes } from "@/components/llm_pipelines/pipelineTypes";
import { PipelineFlavorsList } from "@/components/llm_pipelines/PipelineFlavorsList";

export const Route = createFileRoute("/app/config/pipelines/$pipelineType")({
  component: PipelineTypeConfigPage,
});

function PipelineTypeConfigPage() {
  const { pipelineType } = Route.useParams() as { pipelineType: PipelineType };

  const pipelineConfig = PipelineTypes.find((p) => p.value === pipelineType);

  if (!pipelineConfig) {
    return (
      <Alert color="failure" className="m-4">
        <span className="font-medium">Error!</span> Unknown pipeline type:{" "}
        {pipelineType}
      </Alert>
    );
  }

  return (
    <>
      {/* Breadcrumbs */}
      <Breadcrumb className="mb-4">
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <Link
            to="/app"
            className="flex items-center gap-1 hover:text-blue-600"
          >
            <Home className="h-4 w-4" />
            Home
          </Link>
          <span>/</span>
          <Link to="/app/config" className="hover:text-blue-600">
            Configuration
          </Link>
          <span>/</span>
          <Link to="/app/config/pipelines" className="hover:text-blue-600">
            Pipeline Flavors
          </Link>
          <span>/</span>
          <span className="text-gray-900 dark:text-white">
            {pipelineConfig.label}
          </span>
        </div>
      </Breadcrumb>

      <CsMainTitle>{pipelineConfig.label} Pipeline Flavors</CsMainTitle>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {pipelineConfig.description}
      </p>

      <div className="mt-6 space-y-6">
        {/* Use PipelineFlavorsList component */}
        <PipelineFlavorsList pipelineType={pipelineType} />
      </div>
    </>
  );
}

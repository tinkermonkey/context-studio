import { createFileRoute } from "@tanstack/react-router";
import { ArrowLeft, Home, Settings } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Spinner, Alert, Breadcrumb } from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { PipelineFlavorEditor } from "@/components/llm_pipelines/PipelineFlavorEditor";
import { usePipelineFlavor } from "@/api/hooks/pipelineFlavors";
import type { PipelineType } from "@/api/services/pipelineFlavors";
import { PipelineTypes } from "@/components/llm_pipelines/pipelineTypes";

export const Route = createFileRoute(
  "/app/config/pipelines/$pipelineType/edit/$flavorId",
)({
  component: EditFlavorPage,
});

function EditFlavorPage() {
  const { pipelineType, flavorId } = Route.useParams() as {
    pipelineType: PipelineType;
    flavorId: string;
  };
  const navigate = Route.useNavigate();

  const { data: flavor, isLoading, error } = usePipelineFlavor(flavorId);
  const pipelineConfig = PipelineTypes.find((p) => p.value === pipelineType);

  const handleClose = () => {
    navigate({
      to: "/app/config/pipelines/$pipelineType",
      params: { pipelineType },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner size="lg" />
        <span className="ml-3">Loading flavor...</span>
      </div>
    );
  }

  if (error || !flavor) {
    return (
      <Alert color="failure" className="m-4">
        <span className="font-medium">Error!</span> Unable to load flavor with
        ID: {flavorId}
      </Alert>
    );
  }

  return (
    <>
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
          <Link
            to="/app/config/pipelines/$pipelineType"
            params={{ pipelineType }}
            className="hover:text-blue-600"
          >
            {pipelineConfig?.label}
          </Link>
          <span>/</span>
          <span className="text-gray-900 dark:text-white">{flavor.title}</span>
        </div>
      </Breadcrumb>

      <CsMainTitle >Edit Flavor</CsMainTitle>

      <div className="mt-6">
        <PipelineFlavorEditor
          pipeline={pipelineType}
          flavor={flavor}
          onClose={handleClose}
        />
      </div>
    </>
  );
}

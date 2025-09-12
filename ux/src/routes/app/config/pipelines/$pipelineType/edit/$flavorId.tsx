import { createFileRoute } from "@tanstack/react-router";
import { ArrowLeft, Settings } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Spinner, Alert } from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { PipelineFlavorEditor } from "@/components/llm_pipelines/flavors/PipelineFlavorEditor";
import { usePipelineFlavor } from "@/api/hooks/pipelineFlavors";
import type { PipelineType } from "@/api/services/pipelineFlavors";
import { PipelineTypes } from "@/components/llm_pipelines/flavors/pipelineTypes";

export const Route = createFileRoute("/app/config/pipelines/$pipelineType/edit/$flavorId")({
  component: EditFlavorPage,
});

function EditFlavorPage() {
  const { pipelineType, flavorId } = Route.useParams() as { 
    pipelineType: PipelineType; 
    flavorId: string; 
  };
  const navigate = Route.useNavigate();
  
  const { data: flavor, isLoading, error } = usePipelineFlavor(flavorId);
  const pipelineConfig = PipelineTypes.find(p => p.value === pipelineType);

  const handleClose = () => {
    navigate({ 
      to: "/app/config/pipelines/$pipelineType", 
      params: { pipelineType } 
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
        <span className="font-medium">Error!</span> Unable to load flavor with ID: {flavorId}
      </Alert>
    );
  }

  return (
    <>
      <CsMainTitle icon={Settings}>
        <div className="flex items-center gap-3">
          <Link 
            to="/app/config/pipelines/$pipelineType" 
            params={{ pipelineType }}
            className="hover:text-blue-600"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          Edit {pipelineConfig?.label} Flavor: {flavor.title}
        </div>
      </CsMainTitle>

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
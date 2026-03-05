import { createFileRoute } from "@tanstack/react-router";
// removed import;
import { Link } from "@tanstack/react-router";
import { CsMainTitle } from "@/components/layout/cs_main";
import { PipelineFlavorEditor } from "@/components/llm_pipelines/PipelineFlavorEditor";
import { PipelineTypes } from "@/components/llm_pipelines/pipelineTypes";
import type { PipelineType } from "@/api/services/pipelineFlavors";

export const Route = createFileRoute(
  "/app/config/pipelines/$pipelineType/create",
)({
  component: CreateFlavorPage,
});

function CreateFlavorPage() {
  const { pipelineType } = Route.useParams() as { pipelineType: PipelineType };
  const navigate = Route.useNavigate();
  const pipelineConfig = PipelineTypes.find((p) => p.value === pipelineType);

  const handleClose = () => {
    navigate({
      to: "/app/config/pipelines/$pipelineType",
      params: { pipelineType },
    });
  };

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
          Create New {pipelineConfig?.label} Flavor
        </div>
      </CsMainTitle>

      <div className="mt-6">
        <PipelineFlavorEditor
          pipeline={pipelineType}
          flavor={null}
          onClose={handleClose}
        />
      </div>
    </>
  );
}

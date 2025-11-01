import { createFileRoute } from "@tanstack/react-router";
import { Spinner, Alert } from "flowbite-react";
import { useStructureNode } from "@/api/hooks/structure_nodes/useStructureNodes";
import { StructureNodeDetails } from "@/components/node_details/structure_node_details";

export const Route = createFileRoute("/app/structure_nodes/$nodeId")({
  component: StructureNodeDetailPage,
});

function StructureNodeDetailPage() {
  const { nodeId } = Route.useParams() as { nodeId: string };
  const {
    data: node,
    isLoading: nodeLoading,
    error: nodeError,
  } = useStructureNode(nodeId);

  if (nodeLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner size="lg" aria-label="Loading node..." />
        <span className="ml-3 text-lg">Loading node...</span>
      </div>
    );
  }

  if (nodeError || !node) {
    return (
      <Alert color="failure" className="m-4">
        <span className="font-medium">Error!</span> Unable to load node with ID:{" "}
        {nodeId}
      </Alert>
    );
  }

  return <StructureNodeDetails node={node} />;
}

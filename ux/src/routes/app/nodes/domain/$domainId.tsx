import { createFileRoute } from "@tanstack/react-router";
import { Spinner, Alert } from "flowbite-react";
import { useStructureNode } from "@/api/hooks/structure_nodes/useStructureNodes";
import { DomainDetails } from "@/components/node_details/domain_details";

export const Route = createFileRoute("/app/nodes/domain/$domainId")({
  component: DomainDetailPage,
});

function DomainDetailPage() {
  const { domainId } = Route.useParams() as { domainId: string };
  const {
    data: domain,
    isLoading: domainLoading,
    error: domainError,
  } = useStructureNode(domainId);

  if (domainLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner size="lg" aria-label="Loading domain..." />
        <span className="ml-3 text-lg">Loading domain...</span>
      </div>
    );
  }

  if (domainError || !domain) {
    return (
      <Alert color="failure" className="m-4">
        <span className="font-medium">Error!</span> Unable to load domain with
        ID: {domainId}
      </Alert>
    );
  }

  return <DomainDetails domain={domain} />;
}

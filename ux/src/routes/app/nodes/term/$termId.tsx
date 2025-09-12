import { createFileRoute } from "@tanstack/react-router";
import { Spinner, Alert } from "flowbite-react";
import { useStructureNode } from "@/api/hooks/structure_nodes/useStructureNodes";
import { TermDetails } from "@/components/node_details/term_details";

export const Route = createFileRoute("/app/nodes/term/$termId")({
  component: TermDetailPage,
});

function TermDetailPage() {
  const { termId } = Route.useParams() as { termId: string };
  const {
    data: term,
    isLoading: termLoading,
    error: termError,
  } = useStructureNode(termId);

  if (termLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner size="lg" aria-label="Loading term..." />
        <span className="ml-3 text-lg">Loading term...</span>
      </div>
    );
  }

  if (termError || !term) {
    return (
      <Alert color="failure" className="m-4">
        <span className="font-medium">Error!</span> Unable to load term with ID:{" "}
        {termId}
      </Alert>
    );
  }

  return <TermDetails term={term} />;
}

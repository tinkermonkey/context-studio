import { createFileRoute } from "@tanstack/react-router";
import { useConceptScheme } from "@/api/hooks/conceptSchemes";
import { OntologyClassDetails } from "@/components/node_details/structure_node_details";
import { NodeType } from "@/api/types/ontology";
import { Spinner } from "flowbite-react";
import type { OntologyClass } from "@/api/types/ontology";

export const Route = createFileRoute("/app/concept-schemes/$schemeId")({
  component: ConceptSchemeDetailsPage,
});

function ConceptSchemeDetailsPage() {
  const { schemeId } = Route.useParams();
  const { data: conceptScheme, isLoading, error } = useConceptScheme(schemeId);

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    console.error(error);
    return (
      <div className="p-6">
        <div className="text-red-600">Error loading concept scheme details</div>
      </div>
    );
  }

  if (!conceptScheme) {
    return (
      <div className="p-6">
        <div className="text-gray-600">Concept scheme not found</div>
      </div>
    );
  }

  // Cast concept scheme to OntologyClass with node_type for display component
  const ontologyNode: OntologyClass = {
    ...conceptScheme,
    node_type: NodeType.CONCEPT_SCHEME,
    concept_scheme_id: schemeId,
  } as OntologyClass;

  return <OntologyClassDetails node={ontologyNode} />;
}

import { createFileRoute } from "@tanstack/react-router";
import { useTaxonomy } from "@/api/hooks/taxonomies";
import { OntologyClassDetails } from "@/components/node_details/structure_node_details";
import { NodeType } from "@/api/types/ontology";
import { Spinner } from "flowbite-react";
import type { OntologyClass } from "@/api/types/ontology";

export const Route = createFileRoute("/app/taxonomies/$taxonomyId")({
  component: TaxonomyDetailsPage,
});

function TaxonomyDetailsPage() {
  const { taxonomyId } = Route.useParams();
  const { data: taxonomy, isLoading, error } = useTaxonomy(taxonomyId);

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    console.error(error);
    return (
      <div className="p-6">
        <div className="text-red-600">Error loading taxonomy details</div>
      </div>
    );
  }

  if (!taxonomy) {
    return (
      <div className="p-6">
        <div className="text-gray-600">Taxonomy not found</div>
      </div>
    );
  }

  // Cast taxonomy to OntologyClass with node_type for display component
  const ontologyNode: OntologyClass = {
    ...taxonomy,
    node_type: NodeType.TAXONOMY,
    concept_scheme_id: "",
    taxonomy_id: taxonomyId,
  } as OntologyClass;

  return <OntologyClassDetails node={ontologyNode} />;
}

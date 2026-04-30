import { createFileRoute } from "@tanstack/react-router";
import { useOntologyClass } from "@/api/hooks/ontologyClasses";
import { OntologyClassDetails } from "@/components/node_details/structure_node_details";
import { Spinner } from "flowbite-react";

export const Route = createFileRoute("/app/classes/$classId")({
  component: ClassDetailsPage,
});

function ClassDetailsPage() {
  const { classId } = Route.useParams();
  const { data: ontologyClass, isLoading, error } = useOntologyClass(classId);

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    console.error(error);
    return (
      <div className="p-6">
        <div className="text-red-600">Error loading class details</div>
      </div>
    );
  }

  if (!ontologyClass) {
    return (
      <div className="p-6">
        <div className="text-gray-600">Class not found</div>
      </div>
    );
  }

  return <OntologyClassDetails node={ontologyClass} />;
}

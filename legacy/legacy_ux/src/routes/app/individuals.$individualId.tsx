import { createFileRoute } from "@tanstack/react-router";
import { useIndividual } from "@/api/hooks/individuals";
import { IndividualDetails } from "@/components/node_details/individual_details";
import { Spinner } from "flowbite-react";

export const Route = createFileRoute("/app/individuals/$individualId")({
  component: IndividualDetailsPage,
});

function IndividualDetailsPage() {
  const { individualId } = Route.useParams();
  const { data: individual, isLoading, error } = useIndividual(individualId);

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    console.error(error);
    return (
      <div className="p-6">
        <div className="text-red-600">Error loading individual details</div>
      </div>
    );
  }

  if (!individual) {
    return (
      <div className="p-6">
        <div className="text-gray-600">Individual not found</div>
      </div>
    );
  }

  return <IndividualDetails individual={individual} />;
}

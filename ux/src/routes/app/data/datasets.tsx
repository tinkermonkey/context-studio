import { createFileRoute } from "@tanstack/react-router";
import { EmptyState } from "@/components/ui/EmptyState";
import { datasetsCopy } from "./datasets/-copy";

export const Route = createFileRoute("/app/data/datasets")({
  component: () => (
    <div>
      <EmptyState
        title={datasetsCopy.emptyState.title}
        description={datasetsCopy.emptyState.description}
      />
    </div>
  ),
});

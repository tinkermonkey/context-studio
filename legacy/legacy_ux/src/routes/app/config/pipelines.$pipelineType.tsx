import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/config/pipelines/$pipelineType")({
  // Pathless route - no component needed for flat routing
  // Child routes (index, create, edit, test) are self-contained
});

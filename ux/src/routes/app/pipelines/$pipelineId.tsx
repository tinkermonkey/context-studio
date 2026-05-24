import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/app/pipelines/$pipelineId")({
  beforeLoad: () => {
    throw redirect({ to: "/app/pipelines" });
  },
  component: () => null,
});

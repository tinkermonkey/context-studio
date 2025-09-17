import React from "react";
import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/app/config/pipelines/$pipelineType")({
  component: PipelineTypeLayoutComponent,
});

function PipelineTypeLayoutComponent() {
  return <Outlet />;
}

import React from "react";
import { createFileRoute, Link, Outlet } from "@tanstack/react-router";
import { Card } from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { Settings, ChevronRight } from "lucide-react";
import { PipelineTypes } from "@/components/llm_pipelines/pipelineTypes";

export const Route = createFileRoute("/app/config/pipelines")({
  component: PipelineConfigLayout,
});

function PipelineConfigLayout() {
  return <Outlet />;
}

import React, { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CsMainTitle } from "@/components/layout/cs_main";
import { Settings } from "lucide-react";
import { PipelineFlavorsList } from "@/components/llm_pipelines/flavors/PipelineFlavorsList";

export const Route = createFileRoute("/app/config/pipelines")({
  component: PipelineConfigPage,
});

function PipelineConfigPage() {
  return (
    <>
      <CsMainTitle icon={Settings}>Pipeline Flavors Configuration</CsMainTitle>

      <div className="mt-6">
        <PipelineFlavorsList />
      </div>
    </>
  );
}

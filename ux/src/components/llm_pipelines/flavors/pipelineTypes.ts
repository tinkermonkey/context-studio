import React from "react";
import { Layers, Database, Hash } from "lucide-react";
import type { PipelineType } from "@/api/services/pipelineFlavors";

export interface PipelineTypeConfig {
  value: PipelineType;
  label: string;
  description: string;
  icon: React.ElementType;
}

export const PipelineTypes: PipelineTypeConfig[] = [
  {
    icon: Layers,
    value: "suggest_layer_definition",
    label: "Layer Definitions",
    description: "Generate definitions for knowledge structure layers",
  },
  {
    icon: Database,
    value: "suggest_domain_definition",
    label: "Domain Definitions",
    description: "Generate definitions for knowledge structure domains",
  },
  {
    icon: Hash,
    value: "suggest_term_definition",
    label: "Term Definitions",
    description: "Generate definitions for knowledge structure terms",
  },
];

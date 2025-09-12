import React, { useState } from "react";
import { Button, Card, Spinner, Alert } from "flowbite-react";
import { Plus, Settings } from "lucide-react";
import { usePipelineFlavors } from "@/api/hooks/pipelineFlavors";
import { PipelineFlavorEditor } from "./PipelineFlavorEditor";
import { PipelineFlavorTester } from "../testing/PipelineFlavorTester";
import type {
  PipelineType,
  PipelineFlavor,
} from "@/api/services/pipelineFlavors";

const PIPELINE_TYPES: {
  value: PipelineType;
  label: string;
  description: string;
}[] = [
  {
    value: "suggest_layer_definition",
    label: "Layer Definitions",
    description: "Generate definitions for knowledge layers",
  },
  {
    value: "suggest_domain_definition",
    label: "Domain Definitions",
    description: "Generate definitions for knowledge domains",
  },
  {
    value: "suggest_term_definition",
    label: "Term Definitions",
    description: "Generate definitions for knowledge terms",
  },
];

export const PipelineFlavorsList: React.FC = () => {
  const [selectedPipeline, setSelectedPipeline] = useState<PipelineType>(
    "suggest_layer_definition",
  );
  const [editingFlavor, setEditingFlavor] = useState<PipelineFlavor | null>(
    null,
  );
  const [testingFlavor, setTestingFlavor] = useState<PipelineFlavor | null>(
    null,
  );
  const [showCreateForm, setShowCreateForm] = useState(false);

  const {
    data: flavorsResponse,
    isLoading,
    error,
  } = usePipelineFlavors({ pipeline: selectedPipeline });

  const flavors = flavorsResponse?.flavors || [];

  const handleCreateNew = () => {
    setEditingFlavor(null);
    setShowCreateForm(true);
  };

  const handleEdit = (flavor: PipelineFlavor) => {
    setEditingFlavor(flavor);
    setShowCreateForm(false);
  };

  const handleTest = (flavor: PipelineFlavor) => {
    setTestingFlavor(flavor);
  };

  const handleCloseEditor = () => {
    setEditingFlavor(null);
    setShowCreateForm(false);
  };

  const handleCloseTester = () => {
    setTestingFlavor(null);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner size="lg" />
        <span className="ml-3">Loading pipeline flavors...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Alert color="failure">
        <span className="font-medium">Error loading pipeline flavors:</span>{" "}
        {error.message}
      </Alert>
    );
  }

  // If showing editor or tester, render those instead
  if (showCreateForm || editingFlavor) {
    return (
      <PipelineFlavorEditor
        pipeline={selectedPipeline}
        flavor={editingFlavor}
        onClose={handleCloseEditor}
      />
    );
  }

  if (testingFlavor) {
    return (
      <PipelineFlavorTester
        flavor={testingFlavor}
        onClose={handleCloseTester}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Pipeline Selection */}
      <Card>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Select Pipeline Type
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Choose which pipeline type you want to manage flavors for
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {PIPELINE_TYPES.map((pipeline) => (
            <Button
              key={pipeline.value}
              color={selectedPipeline === pipeline.value ? "blue" : "gray"}
              onClick={() => setSelectedPipeline(pipeline.value)}
              className="min-w-0 flex-1"
            >
              <Settings className="mr-2 h-4 w-4" />
              {pipeline.label}
            </Button>
          ))}
        </div>

        <div className="mt-3 rounded-lg bg-gray-50 p-3 dark:bg-gray-800">
          <p className="text-sm text-gray-600 dark:text-gray-300">
            {
              PIPELINE_TYPES.find((p) => p.value === selectedPipeline)
                ?.description
            }
          </p>
        </div>
      </Card>

      {/* Flavors Management */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {PIPELINE_TYPES.find((p) => p.value === selectedPipeline)?.label}{" "}
              Flavors
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Manage configuration variants for this pipeline type
            </p>
          </div>
          <Button onClick={handleCreateNew} color="blue">
            <Plus className="mr-2 h-4 w-4" />
            Create New Flavor
          </Button>
        </div>

        {flavors.length === 0 ? (
          <div className="py-8 text-center text-gray-500 dark:text-gray-400">
            <Settings className="mx-auto mb-4 h-12 w-12 opacity-50" />
            <h4 className="mb-2 text-lg font-medium">No flavors configured</h4>
            <p className="mb-4 text-sm">
              Create your first flavor configuration for this pipeline type
            </p>
            <Button onClick={handleCreateNew} color="blue" size="sm">
              <Plus className="mr-2 h-4 w-4" />
              Create First Flavor
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {flavors.map((flavor) => (
              <div
                key={flavor.id}
                className="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white">
                      {flavor.title}
                    </h4>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Provider: {flavor.llm_provider} | Model:{" "}
                      {flavor.llm_model} | Version: {flavor.version}
                    </p>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
                      {flavor.enabled ? "Enabled" : "Disabled"} | Created:{" "}
                      {new Date(flavor.date_created).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      color="gray"
                      onClick={() => handleEdit(flavor)}
                      disabled={flavor.title === "Default"}
                      title={
                        flavor.title === "Default"
                          ? "The Default flavor cannot be edited or deleted."
                          : undefined
                      }
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      color="blue"
                      onClick={() => handleTest(flavor)}
                    >
                      Test
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

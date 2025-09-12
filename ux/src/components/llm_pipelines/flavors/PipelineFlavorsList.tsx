import React, { useState } from "react";
import { Button, Card, Spinner, Alert } from "flowbite-react";
import { Plus, Settings } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { usePipelineFlavors } from "@/api/hooks/pipelineFlavors";
import type {
  PipelineType,
  PipelineFlavor,
} from "@/api/services/pipelineFlavors";
import { PipelineTypes } from "./pipelineTypes";

export interface PipelineFlavorsListProps {
  selectedPipelineOverride?: PipelineType;
}

export const PipelineFlavorsList: React.FC<PipelineFlavorsListProps> = ({
  selectedPipelineOverride,
}) => {
  const [selectedPipeline, setSelectedPipeline] = useState<PipelineType>(
    selectedPipelineOverride || "suggest_layer_definition",
  );

  // Use override if provided, otherwise use selected pipeline
  const activePipeline = selectedPipelineOverride || selectedPipeline;

  const {
    data: flavorsResponse,
    isLoading,
    error,
  } = usePipelineFlavors({ pipeline: activePipeline });

  const flavors = flavorsResponse?.flavors || [];

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

  return (
    <div className="space-y-6">
      {/* Pipeline Selection - only show when not using override */}
      {!selectedPipelineOverride && (
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
            {PipelineTypes.map((pipeline) => (
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
                PipelineTypes.find((p) => p.value === selectedPipeline)
                  ?.description
              }
            </p>
          </div>
        </Card>
      )}

      {/* Flavors Management */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {PipelineTypes.find((p) => p.value === activePipeline)?.label}{" "}
              Flavors
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Manage configuration variants for this pipeline type
            </p>
          </div>
          <Link
            to="/app/config/pipelines/$pipelineType/create"
            params={{ pipelineType: activePipeline }}
          >
            <Button color="blue">
              <Plus className="mr-2 h-4 w-4" />
              Create New Flavor
            </Button>
          </Link>
        </div>

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
                    Provider: {flavor.llm_provider} | Model: {flavor.llm_model}{" "}
                    | Version: {flavor.version}
                  </p>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
                    {flavor.enabled ? "Enabled" : "Disabled"} | Created:{" "}
                    {new Date(flavor.date_created).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Link
                    to="/app/config/pipelines/$pipelineType/edit/$flavorId"
                    params={{
                      pipelineType: activePipeline,
                      flavorId: flavor.id,
                    }}
                  >
                    <Button
                      size="sm"
                      color="gray"
                      disabled={flavor.title === "Default"}
                      title={
                        flavor.title === "Default"
                          ? "The Default flavor cannot be edited or deleted."
                          : undefined
                      }
                    >
                      Edit
                    </Button>
                  </Link>
                  <Link
                    to="/app/config/pipelines/$pipelineType/test/$flavorId"
                    params={{
                      pipelineType: activePipeline,
                      flavorId: flavor.id,
                    }}
                  >
                    <Button size="sm" color="blue">
                      Test
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

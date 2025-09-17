import React, { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Button, Card, Spinner, Alert } from "flowbite-react";
import { Plus, Settings, ArrowLeft } from "lucide-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { usePipelineFlavors } from "@/api/hooks/pipelineFlavors";
import type {
  PipelineType,
  PipelineFlavor,
} from "@/api/services/pipelineFlavors";
import { PipelineTypes } from "@/components/llm_pipelines/flavors/pipelineTypes";

export const Route = createFileRoute("/app/config/pipelines/$pipelineType/")({
  component: PipelineTypeConfigPage,
});

function PipelineTypeConfigPage() {
  const { pipelineType } = Route.useParams() as { pipelineType: PipelineType };

  const {
    data: flavorsResponse,
    isLoading,
    error,
  } = usePipelineFlavors({ pipeline: pipelineType });

  const flavors = flavorsResponse?.flavors || [];
  const pipelineConfig = PipelineTypes.find((p) => p.value === pipelineType);

  if (!pipelineConfig) {
    return (
      <Alert color="failure" className="m-4">
        <span className="font-medium">Error!</span> Unknown pipeline type:{" "}
        {pipelineType}
      </Alert>
    );
  }

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
    <>
      <CsMainTitle icon={Settings}>
        <div className="flex items-center gap-3">
          <Link to="/app/config/pipelines" className="hover:text-blue-600">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          {pipelineConfig.label} Configuration
        </div>
      </CsMainTitle>

      <div className="mt-6 space-y-6">
        {/* Pipeline Info */}
        <Card>
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {pipelineConfig.label}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {pipelineConfig.description}
            </p>
          </div>
        </Card>

        {/* Flavors Management */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Flavor Configurations
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Manage configuration variants for this pipeline type
              </p>
            </div>
            <Link
              to="/app/config/pipelines/$pipelineType/create"
              params={{ pipelineType }}
            >
              <Button color="blue">
                <Plus className="mr-2 h-4 w-4" />
                Create New Flavor
              </Button>
            </Link>
          </div>

          {flavors.length === 0 ? (
            <div className="py-8 text-center text-gray-500 dark:text-gray-400">
              <Settings className="mx-auto mb-4 h-12 w-12 opacity-50" />
              <h4 className="mb-2 text-lg font-medium">
                No flavors configured
              </h4>
              <p className="mb-4 text-sm">
                Create your first flavor configuration for this pipeline type
              </p>
              <Link
                to="/app/config/pipelines/$pipelineType/create"
                params={{ pipelineType }}
              >
                <Button color="blue" size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  Create First Flavor
                </Button>
              </Link>
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
                      <Link
                        to="/app/config/pipelines/$pipelineType/edit/$flavorId"
                        params={{ pipelineType, flavorId: flavor.id }}
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
                        params={{ pipelineType, flavorId: flavor.id }}
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
          )}
        </Card>
      </div>
    </>
  );
}

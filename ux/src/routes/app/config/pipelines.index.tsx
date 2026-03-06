import React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Breadcrumb } from "flowbite-react";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ChevronRight, Home, Settings } from "lucide-react";;
import { PipelineTypes } from "@/components/llm_pipelines/pipelineTypes";

export const Route = createFileRoute("/app/config/pipelines/")({
  component: PipelineConfigIndexPage,
});

function PipelineConfigIndexPage() {
  // Show pipeline type selection
  return (
    <>
      {/* Breadcrumbs */}
      <Breadcrumb className="mb-4">
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <Link
            to="/app"
            className="flex items-center gap-1 hover:text-blue-600"
          >
            <Home className="h-4 w-4" />
            Home
          </Link>
          <span>/</span>
          <Link to="/app/config" className="hover:text-blue-600">
            Configuration
          </Link>
          <span>/</span>
          <span className="text-gray-900 dark:text-white">
            Pipeline Flavors
          </span>
        </div>
      </Breadcrumb>

      <CsMainTitle>Pipeline Flavor Configuration</CsMainTitle>

      <div className="mt-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Select Pipeline Type
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Choose which pipeline type you want to manage flavors for
          </p>
        </div>

        <div className="space-y-4">
          {PipelineTypes.map((pipeline) => (
            <Link
              key={pipeline.value}
              to="/app/config/pipelines/$pipelineType"
              params={{ pipelineType: pipeline.value }}
              className="block w-full"
            >
              <div className="group rounded-lg border border-gray-200 p-4 transition-all hover:border-blue-300 hover:bg-blue-50 dark:border-gray-700 dark:hover:border-blue-600 dark:hover:bg-blue-900/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="text-2xl">
                      {React.createElement(pipeline.icon)}
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900 group-hover:text-blue-600 dark:text-white dark:group-hover:text-blue-400">
                        {pipeline.label}
                      </h4>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {pipeline.description}
                      </p>
                    </div>
                  </div>
                  <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-blue-600 dark:group-hover:text-blue-400" />
                </div>
              </div>
            </Link>
          ))}
        </div>

        <div className="mt-6 rounded-lg bg-gray-50 p-4 dark:bg-gray-800">
          <div className="flex items-center gap-3">
            <Settings className="h-5 w-5 text-gray-600 dark:text-gray-400" />
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                Pipeline Flavors
              </p>
              <p className="text-xs text-gray-600 dark:text-gray-400">
                Each pipeline type can have multiple flavors with different
                configurations for LLM providers, models, and prompts.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

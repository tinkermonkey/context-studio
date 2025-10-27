/**
 * PipelineTestRunner Component
 *
 * Interface for selecting pipelines and test paragraphs, then running parallel tests
 */

import React, { useState } from "react";
import { Button, Label, Spinner, Progress, Checkbox } from "flowbite-react";
import { Play, CheckCircle, XCircle } from "lucide-react";
import {
  useTestParagraphs,
  useRunPipelineTest,
} from "@/api/hooks/ragExperiments";
import type {
  RunPipelineTestResponse,
  PipelineRunResultResponse,
} from "@/api/services/ragExperiments";

export interface PipelineTestRunnerProps {
  onTestComplete?: (results: RunPipelineTestResponse) => void;
}

// Available RAG pipelines
// Note: These are Python pipeline classes registered in the RAG pipeline registry,
// not to be confused with LLM pipeline flavors. Currently hardcoded as there's only
// one RAG pipeline implementation. A future enhancement could add an API endpoint
// to list registered RAG pipeline classes dynamically.
const AVAILABLE_PIPELINES = [
  {
    name: "StandardRAGPipeline",
    description: "Standard baseline RAG pipeline with default configurations",
  },
];

export const PipelineTestRunner: React.FC<PipelineTestRunnerProps> = ({
  onTestComplete,
}) => {
  const [selectedPipelines, setSelectedPipelines] = useState<string[]>([
    "StandardRAGPipeline",
  ]);
  const [selectedParagraphs, setSelectedParagraphs] = useState<string[]>([]);
  const [enableTrace, setEnableTrace] = useState(false);
  const [enableLlmLayer, setEnableLlmLayer] = useState(true);

  const { data: paragraphsData, isLoading: paragraphsLoading } =
    useTestParagraphs({ limit: 100 });
  const runTestMutation = useRunPipelineTest();

  const paragraphs = paragraphsData?.paragraphs || [];

  const handlePipelineToggle = (pipelineName: string) => {
    setSelectedPipelines((prev) =>
      prev.includes(pipelineName)
        ? prev.filter((p) => p !== pipelineName)
        : [...prev, pipelineName]
    );
  };

  const handleParagraphToggle = (paragraphId: string) => {
    setSelectedParagraphs((prev) =>
      prev.includes(paragraphId)
        ? prev.filter((p) => p !== paragraphId)
        : [...prev, paragraphId]
    );
  };

  const handleSelectAllParagraphs = () => {
    if (selectedParagraphs.length === paragraphs.length) {
      setSelectedParagraphs([]);
    } else {
      setSelectedParagraphs(paragraphs.map((p) => p.id));
    }
  };

  const handleRunTests = async () => {
    if (selectedPipelines.length === 0 || selectedParagraphs.length === 0) {
      return;
    }

    const results = await runTestMutation.mutateAsync({
      paragraphIds: selectedParagraphs,
      pipelineNames: selectedPipelines,
      enableTrace,
      enableLlmLayer,
    });

    onTestComplete?.(results);
  };

  const totalTests = selectedPipelines.length * selectedParagraphs.length;
  const isRunning = runTestMutation.isPending;
  const canRun = selectedPipelines.length > 0 && selectedParagraphs.length > 0;

  // Calculate progress if running
  let progress = 0;
  let completedCount = 0;
  if (runTestMutation.data) {
    completedCount = runTestMutation.data.results.length;
    progress = totalTests > 0 ? (completedCount / totalTests) * 100 : 0;
  }

  return (
    <div className="space-y-6">
      {/* Pipeline Selection */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-lg font-medium text-gray-900">
          Select Pipelines
        </h3>
        <div className="space-y-2">
          {AVAILABLE_PIPELINES.map((pipeline) => (
            <div key={pipeline.name} className="flex items-start gap-3">
              <Checkbox
                id={`pipeline-${pipeline.name}`}
                checked={selectedPipelines.includes(pipeline.name)}
                onChange={() => handlePipelineToggle(pipeline.name)}
                disabled={isRunning}
              />
              <div className="flex-1">
                <Label
                  htmlFor={`pipeline-${pipeline.name}`}
                  className="font-medium"
                >
                  {pipeline.name}
                </Label>
                <p className="text-sm text-gray-600">{pipeline.description}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-sm text-gray-500">
          {selectedPipelines.length} pipeline(s) selected
        </p>
      </div>

      {/* Test Paragraph Selection */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">
            Select Test Paragraphs
          </h3>
          {paragraphs.length > 0 && (
            <Button
              size="xs"
              color="gray"
              onClick={handleSelectAllParagraphs}
              disabled={isRunning}
            >
              {selectedParagraphs.length === paragraphs.length
                ? "Deselect All"
                : "Select All"}
            </Button>
          )}
        </div>

        {paragraphsLoading ? (
          <div className="flex items-center gap-2 py-4">
            <Spinner size="sm" />
            <span className="text-sm text-gray-500">
              Loading test paragraphs...
            </span>
          </div>
        ) : paragraphs.length === 0 ? (
          <div className="py-4 text-center text-sm text-gray-500">
            No test paragraphs available. Create some paragraphs first.
          </div>
        ) : (
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {paragraphs.map((paragraph) => (
              <div key={paragraph.id} className="flex items-start gap-3">
                <Checkbox
                  id={`paragraph-${paragraph.id}`}
                  checked={selectedParagraphs.includes(paragraph.id)}
                  onChange={() => handleParagraphToggle(paragraph.id)}
                  disabled={isRunning}
                />
                <div className="flex-1">
                  <Label
                    htmlFor={`paragraph-${paragraph.id}`}
                    className="font-medium"
                  >
                    <span className="line-clamp-1">
                      {paragraph.text.substring(0, 100)}
                      {paragraph.text.length > 100 ? "..." : ""}
                    </span>
                  </Label>
                  {paragraph.notes && (
                    <p className="text-xs text-gray-600">{paragraph.notes}</p>
                  )}
                  <p className="text-xs text-gray-500">
                    {paragraph.annotations?.length || 0} annotation(s)
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 text-sm text-gray-500">
          {selectedParagraphs.length} paragraph(s) selected
        </p>
      </div>

      {/* Options */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-lg font-medium text-gray-900">Options</h3>
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <Checkbox
              id="enable-trace"
              checked={enableTrace}
              onChange={(e) => setEnableTrace(e.target.checked)}
              disabled={isRunning}
            />
            <Label htmlFor="enable-trace">
              <span className="font-medium">Enable Detailed Tracing</span>
              <p className="text-sm text-gray-600">
                Collect detailed execution traces for debugging
              </p>
            </Label>
          </div>
          <div className="flex items-center gap-3">
            <Checkbox
              id="enable-llm-layer"
              checked={enableLlmLayer}
              onChange={(e) => setEnableLlmLayer(e.target.checked)}
              disabled={isRunning}
            />
            <Label htmlFor="enable-llm-layer">
              <span className="font-medium">Enable LLM Layer</span>
              <p className="text-sm text-gray-600">
                Use LLM for entity extraction (Layer 1)
              </p>
            </Label>
          </div>
        </div>
      </div>

      {/* Run Tests Button and Progress */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">
                Total Tests: {totalTests}
              </p>
              <p className="text-xs text-gray-600">
                {selectedPipelines.length} pipeline(s) × {selectedParagraphs.length} paragraph(s)
              </p>
            </div>
            <Button
              onClick={handleRunTests}
              disabled={!canRun || isRunning}
              size="lg"
            >
              {isRunning ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Running Tests...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-5 w-5" />
                  Run Tests
                </>
              )}
            </Button>
          </div>

          {/* Progress Bar */}
          {isRunning && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-700">
                  Progress: {completedCount} / {totalTests}
                </span>
                <span className="font-medium text-gray-900">
                  {progress.toFixed(0)}%
                </span>
              </div>
              <Progress progress={progress} size="lg" color="blue" />
            </div>
          )}

          {/* Results Summary */}
          {runTestMutation.isSuccess && runTestMutation.data && (
            <div className="rounded-lg bg-green-50 p-4">
              <div className="flex items-center gap-2 text-green-800">
                <CheckCircle className="h-5 w-5" />
                <span className="font-medium">Tests Completed!</span>
              </div>
              <div className="mt-2 space-y-1 text-sm text-green-700">
                <p>
                  Total Runs: {runTestMutation.data.total_runs}
                </p>
                <p>
                  Successful: {runTestMutation.data.successful_runs}
                </p>
                <p>
                  Failed: {runTestMutation.data.failed_runs}
                </p>
              </div>
            </div>
          )}

          {/* Error Display */}
          {runTestMutation.error && (
            <div className="rounded-lg bg-red-50 p-4">
              <div className="flex items-center gap-2 text-red-800">
                <XCircle className="h-5 w-5" />
                <span className="font-medium">Error Running Tests</span>
              </div>
              <p className="mt-2 text-sm text-red-700">
                {runTestMutation.error.message}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

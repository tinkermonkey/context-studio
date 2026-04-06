/**
 * RAG Test Page
 *
 * Test interface for the RAG entity extraction API endpoint
 */

import { useState, useMemo } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Label,
  Spinner,
  Textarea,
} from "flowbite-react";
import { useExtractEntities, useRAGTrace } from "@/api/hooks/rag";
import { useStructureNode } from "@/api/hooks/structure_nodes/useStructureNodes";
import { Info, ExternalLink } from "lucide-react";
import { Link } from "@tanstack/react-router";

// Component to render a single entity with its matched node link

function EntityItem(
  { entity }: { entity: any }, // eslint-disable-line @typescript-eslint/no-explicit-any
) {
  const { data: node, isLoading } = useStructureNode(
    entity.metadata?.matched_kg_node,
  );

  const linkProps = useMemo(() => {
    if (!node?.id || !node?.node_type) return null;

    return {
      to: "/app/structure_nodes/$nodeId" as const,
      params: { nodeId: node.id },
    };
  }, [node]);

  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-700">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900 dark:text-white">
            {entity.text}
          </span>
          {entity.type && (
            <Badge color="info" size="sm">
              {entity.type}
            </Badge>
          )}
        </div>
        {entity.metadata?.matched_kg_node && (
          <div className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            <span className="font-medium">Matched to:</span>{" "}
            {isLoading ? (
              <span className="italic">Loading...</span>
            ) : (
              node?.title || entity.metadata.matched_kg_node_title || "Unknown"
            )}
          </div>
        )}
        {entity.context && (
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            {entity.context}
          </p>
        )}
        {entity.source_layer && (
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">
            Source: {entity.source_layer}
          </p>
        )}
      </div>
      {linkProps && (
        <Link
          {...linkProps}
          className="ml-4 flex items-center gap-1 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
        >
          <span className="text-sm">View Node</span>
          <ExternalLink className="h-4 w-4" />
        </Link>
      )}
    </div>
  );
}

export default function RAGTestPage() {
  const [inputText, setInputText] = useState("");
  const [enableTrace, setEnableTrace] = useState(true);
  const [enableLlmLayer, setEnableLlmLayer] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [result, setResult] = useState<any>(null);
  const [requestId, setRequestId] = useState<string | null>(null);

  const {
    mutate: extractEntities,
    isPending,
    error,
  } = useExtractEntities({
    onSuccess: (data) => {
      setResult(data);
      // Set request ID to trigger trace fetch
      setRequestId(data.id);
    },
    onError: (err) => {
      console.error("RAG extraction failed:", err);
    },
  });

  // Fetch trace data when request ID is set and trace is available
  const {
    data: traceData,
    isLoading: isLoadingTrace,
    error: traceError,
  } = useRAGTrace(requestId);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) {
      return;
    }
    setResult(null);
    extractEntities({ text: inputText, enableTrace, enableLlmLayer });
  };

  const handleClear = () => {
    setInputText("");
    setResult(null);
    setRequestId(null);
  };

  return (
    <div className="container mx-auto p-4">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          RAG Pipeline Test
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Test the RAG (Retrieval-Augmented Generation) entity extraction
          pipeline
        </p>
      </div>

      <Card className="mb-6">
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <div className="mb-2 flex items-center justify-between">
              <Label htmlFor="input-text">Input Text</Label>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="enable-llm-layer"
                    checked={enableLlmLayer}
                    onChange={(e) => setEnableLlmLayer(e.target.checked)}
                  />
                  <Label htmlFor="enable-llm-layer">Enable LLM Layer</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="enable-trace"
                    checked={enableTrace}
                    onChange={(e) => setEnableTrace(e.target.checked)}
                  />
                  <Label htmlFor="enable-trace">Enable Trace</Label>
                </div>
              </div>
            </div>
            <Textarea
              id="input-text"
              placeholder="Enter text to analyze and extract entities from..."
              rows={8}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isPending}
              className="font-mono"
            />
          </div>

          <Alert color="info" icon={Info} className="mb-4">
            <span className="text-sm">
              The RAG pipeline processes text through four layers: (1) Knowledge
              Graph Context Preparation, (2) LLM-based Entity Extraction, (3)
              spaCy Syntactic Gap Analysis, and (4) Concept Resolution via KG
              and Web Search.
            </span>
          </Alert>

          <div className="flex gap-2">
            <Button
              type="submit"
              disabled={!inputText.trim() || isPending}
              color="blue"
            >
              {isPending ? (
                <>
                  <Spinner size="sm" light className="mr-2" />
                  Processing...
                </>
              ) : (
                "Extract Entities"
              )}
            </Button>
            <Button
              type="button"
              color="gray"
              onClick={handleClear}
              disabled={isPending}
            >
              Clear
            </Button>
          </div>
        </form>
      </Card>

      {error && (
        <Alert color="failure" className="mb-6">
          <span className="font-medium">Error:</span> {error.message}
        </Alert>
      )}

      {result && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Results
            </h2>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Request ID: <code className="font-mono">{result.request_id}</code>
            </div>
          </div>

          <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Total Entities
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {result.metrics.total_entities}
              </div>
            </div>
            <div className="rounded-lg bg-green-50 p-4 dark:bg-green-900/20">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Sentences
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {result.metrics.total_sentences}
              </div>
            </div>
            <div className="rounded-lg bg-purple-50 p-4 dark:bg-purple-900/20">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Execution Time
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {(result.metrics.total_execution_time_ms / 1000).toFixed(1)}s
              </div>
            </div>
            <div className="rounded-lg bg-yellow-50 p-4 dark:bg-yellow-900/20">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Trace Available
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {result.trace_available ? "Yes" : "No"}
              </div>
            </div>
          </div>

          <div className="mb-4">
            <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
              Layer Metrics
            </h3>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
              {Object.entries(result.metrics).map(([key, value]) => {
                if (
                  key.endsWith("_layer") &&
                  typeof value === "object" &&
                  value !== null
                ) {
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  const layerMetrics = value as any;
                  return (
                    <div
                      key={key}
                      className="rounded-lg border border-gray-200 p-3 dark:border-gray-700"
                    >
                      <div className="mb-2 font-semibold text-gray-900 dark:text-white">
                        {key.replace("_layer", "").toUpperCase()}
                      </div>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">
                            Time:
                          </span>
                          <span className="font-mono text-gray-900 dark:text-white">
                            {(layerMetrics.execution_time_ms / 1000).toFixed(1)}
                            s
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">
                            Operations:
                          </span>
                          <span className="font-mono text-gray-900 dark:text-white">
                            {layerMetrics.operations_performed ?? 0}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">
                            Found:
                          </span>
                          <span className="font-mono text-gray-900 dark:text-white">
                            {layerMetrics.entities_found}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">
                            Deduped:
                          </span>
                          <span className="font-mono text-gray-900 dark:text-white">
                            {layerMetrics.entities_deduplicated}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                }
                return null;
              })}
            </div>
          </div>

          {result.entities && result.entities.length > 0 && (
            <div className="mb-4">
              <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
                Extracted Entities ({result.entities.length})
              </h3>
              <div className="space-y-2">
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                {result.entities.map(
                  (
                    entity: any, // eslint-disable-line @typescript-eslint/no-explicit-any
                    index: number,
                  ) => (
                    <EntityItem key={index} entity={entity} />
                  ),
                )}
              </div>
            </div>
          )}

          <div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
              Full Response (JSON)
            </h3>
            <pre className="overflow-auto rounded-lg bg-gray-50 p-4 text-xs dark:bg-gray-900">
              <code className="text-gray-900 dark:text-white">
                {JSON.stringify(result, null, 2)}
              </code>
            </pre>
          </div>
        </Card>
      )}

      {result?.trace_available && (
        <Card className="mt-6">
          <div className="mb-4">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Trace Data
            </h2>
          </div>

          {isLoadingTrace && (
            <div className="flex items-center justify-center py-8">
              <Spinner size="lg" />
              <span className="ml-3 text-gray-600 dark:text-gray-400">
                Loading trace data...
              </span>
            </div>
          )}

          {traceError && (
            <Alert color="failure">
              <span className="font-medium">Error loading trace:</span>{" "}
              {traceError.message}
            </Alert>
          )}

          {traceData ? (
            <div>
              <pre className="overflow-auto rounded-lg bg-gray-50 p-4 text-xs dark:bg-gray-900">
                <code className="text-gray-900 dark:text-white">
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {JSON.stringify(traceData as any, null, 2)}
                </code>
              </pre>
            </div>
          ) : null}
        </Card>
      )}
    </div>
  );
}

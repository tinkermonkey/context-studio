/**
 * RAG Test Page
 *
 * Test interface for the RAG entity extraction API endpoint
 */

import { useState } from "react";
import { Button, Card, Label, Textarea, Spinner, Alert } from "flowbite-react";
import { useExtractEntities } from "@/api/hooks/rag";
import { Info } from "lucide-react";

export default function RAGTestPage() {
  const [inputText, setInputText] = useState("");
  const [enableTrace, setEnableTrace] = useState(false);
  const [result, setResult] = useState<any>(null);

  const { mutate: extractEntities, isPending, error } = useExtractEntities({
    onSuccess: (data) => {
      setResult(data);
    },
    onError: (err) => {
      console.error("RAG extraction failed:", err);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) {
      return;
    }
    setResult(null);
    extractEntities({ text: inputText, enableTrace });
  };

  const handleClear = () => {
    setInputText("");
    setResult(null);
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
              <Label htmlFor="input-text" value="Input Text" />
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="enable-trace"
                  checked={enableTrace}
                  onChange={(e) => setEnableTrace(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 bg-gray-100 text-blue-600 focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:ring-offset-gray-800 dark:focus:ring-blue-600"
                />
                <Label htmlFor="enable-trace" value="Enable Trace" />
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
                {result.metrics.total_execution_time_ms}ms
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
                            {layerMetrics.execution_time_ms}ms
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
    </div>
  );
}

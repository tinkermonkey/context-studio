import React, { useState } from "react";
import { Button, Card, Alert, Select, Label, Spinner } from "flowbite-react";
import { ArrowLeft, TestTube, Play } from "lucide-react";
import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";
import { useLayers } from "@/api/hooks/layers";
import { useDomains } from "@/api/hooks/domains";
import { useTerms } from "@/api/hooks/terms";
import type { PipelineFlavor } from "@/api/services/pipelineFlavors";

interface PipelineFlavorTesterProps {
  flavor: PipelineFlavor;
  onClose: () => void;
}

interface TestRecord {
  id: string;
  title: string;
  type: 'layer' | 'domain' | 'term';
}

export const PipelineFlavorTester: React.FC<PipelineFlavorTesterProps> = ({
  flavor,
  onClose
}) => {
  const [selectedRecord, setSelectedRecord] = useState<TestRecord | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [isTestingPipeline, setIsTestingPipeline] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  // Fetch data based on pipeline type - only fetch what we need
  const { data: layersData, isLoading: layersLoading } = useLayers();
  const { data: domainsData, isLoading: domainsLoading } = useDomains();
  const { data: termsData, isLoading: termsLoading } = useTerms();

  const getRecordOptions = (): TestRecord[] => {
    switch (flavor.pipeline) {
      case "suggest_layer_definition":
        return (layersData || []).map(layer => ({
          id: layer.id,
          title: layer.title,
          type: 'layer' as const
        }));
      case "suggest_domain_definition":
        return (domainsData || []).map(domain => ({
          id: domain.id,
          title: domain.title,
          type: 'domain' as const
        }));
      case "suggest_term_definition":
        return (termsData || []).map(term => ({
          id: term.id,
          title: term.title,
          type: 'term' as const
        }));
      default:
        return [];
    }
  };

  const getPipelineDisplayName = () => {
    return flavor.pipeline.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
  };

  const getRecordTypeDisplayName = () => {
    switch (flavor.pipeline) {
      case "suggest_layer_definition":
        return "Layer";
      case "suggest_domain_definition":
        return "Domain";
      case "suggest_term_definition":
        return "Term";
      default:
        return "Record";
    }
  };

  const handleTestPipeline = async () => {
    if (!selectedRecord) return;

    setIsTestingPipeline(true);
    setPipelineError(null);
    setTestResult(null);

    try {
      // Here you would call your LLM pipeline with the flavor configuration
      // For now, I'll simulate the API call
      await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate API delay
      
      // This would be replaced with actual pipeline execution
      const mockResult = `Generated definition for "${selectedRecord.title}" using flavor "${flavor.title}":

This is a simulated response that would come from your LLM pipeline using the configured prompts and settings.

Provider: ${flavor.llm_provider}
Model: ${flavor.llm_model}
Temperature: ${flavor.llm_config.temperature}

The actual implementation would:
1. Take the selected ${selectedRecord.type} title: "${selectedRecord.title}"
2. Apply the system prompt: "${flavor.system_prompt.substring(0, 100)}..."
3. Format the user prompt template with the record data
4. Send to ${flavor.llm_provider} ${flavor.llm_model}
5. Return the generated definition`;

      setTestResult(mockResult);
    } catch (error) {
      setPipelineError(error instanceof Error ? error.message : "Pipeline execution failed");
    } finally {
      setIsTestingPipeline(false);
    }
  };

  const recordOptions = getRecordOptions();
  const isLoading = layersLoading || domainsLoading || termsLoading;

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <div className="flex items-center gap-3 mb-4">
          <Button color="gray" size="sm" onClick={onClose}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Test Pipeline Flavor: {flavor.title}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {getPipelineDisplayName()} • {flavor.llm_provider} {flavor.llm_model}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="test-record">Select {getRecordTypeDisplayName()} to Test</Label>
            {isLoading ? (
              <div className="flex items-center gap-2 p-3 border rounded-lg">
                <Spinner size="sm" />
                <span className="text-sm">Loading {getRecordTypeDisplayName().toLowerCase()}s...</span>
              </div>
            ) : (
              <Select
                id="test-record"
                value={selectedRecord?.id || ""}
                onChange={(e) => {
                  const option = recordOptions.find(r => r.id === e.target.value);
                  setSelectedRecord(option || null);
                }}
              >
                <option value="">Select a {getRecordTypeDisplayName().toLowerCase()}...</option>
                {recordOptions.map(record => (
                  <option key={record.id} value={record.id}>
                    {record.title}
                  </option>
                ))}
              </Select>
            )}
          </div>

          <div className="flex items-end">
            <Button
              onClick={handleTestPipeline}
              disabled={!selectedRecord || isTestingPipeline}
              color="blue"
              className="w-full"
            >
              {isTestingPipeline ? (
                <Spinner size="sm" className="mr-2" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              {isTestingPipeline ? "Running Pipeline..." : "Test Pipeline"}
            </Button>
          </div>
        </div>
      </Card>

      {/* NLP Analysis Panel */}
      {selectedRecord && (
        <Card>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            NLP Analysis for "{selectedRecord.title}"
          </h3>
          <NlpAnalysisPanel
            text={selectedRecord.title}
            textTitle={selectedRecord.title}
            {...(selectedRecord.type === 'layer' && { layerId: selectedRecord.id })}
            {...(selectedRecord.type === 'domain' && { domainId: selectedRecord.id })}
            {...(selectedRecord.type === 'term' && { termId: selectedRecord.id })}
          />
        </Card>
      )}

      {/* Pipeline Test Results */}
      {pipelineError && (
        <Alert color="failure">
          <div>
            <h4 className="font-medium mb-2">Pipeline Execution Error</h4>
            <p>{pipelineError}</p>
          </div>
        </Alert>
      )}

      {testResult && (
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <TestTube className="h-5 w-5 text-green-600" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Pipeline Test Results
            </h3>
          </div>
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
            <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
              {testResult}
            </pre>
          </div>
          
          <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            <p><strong>Note:</strong> This is a simulation. The actual implementation would integrate with your LLM pipeline service to execute the configured prompts and return real results.</p>
          </div>
        </Card>
      )}
    </div>
  );
};

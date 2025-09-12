import React, { useState } from "react";
import { Button, Card, Select, Label, Spinner } from "flowbite-react";
import { ArrowLeft, BarChart3, Clock } from "lucide-react";
import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";
import { AnalyticsDashboard } from "@/components/llm_traceability/AnalyticsDashboard";
import { ExecutionHistory } from "@/components/llm_traceability/ExecutionHistory";
import {
  useLayerNodes,
  useDomainNodes,
  useTermNodes,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import type { PipelineFlavor } from "@/api/services/pipelineFlavors";

interface PipelineFlavorTesterProps {
  flavor: PipelineFlavor;
  onClose: () => void;
}

interface TestRecord {
  id: string;
  title: string;
  type: "layer" | "domain" | "term";
}

export const PipelineFlavorTester: React.FC<PipelineFlavorTesterProps> = ({
  flavor,
  onClose,
}) => {
  const [selectedRecord, setSelectedRecord] = useState<TestRecord | null>(null);
  const [activeView, setActiveView] = useState<"analytics" | "history">("analytics");
  // Fetch data based on pipeline type - only fetch what we need
  const { data: layersData, isLoading: layersLoading } = useLayerNodes();
  const { data: domainsData, isLoading: domainsLoading } = useDomainNodes();
  const { data: termsData, isLoading: termsLoading } = useTermNodes();

  const getRecordOptions = (): TestRecord[] => {
    switch (flavor.pipeline) {
      case "suggest_layer_definition":
        return (layersData || []).map((layer) => ({
          id: layer.id,
          title: layer.title,
          type: "layer" as const,
        }));
      case "suggest_domain_definition":
        return (domainsData || []).map((domain) => ({
          id: domain.id,
          title: domain.title,
          type: "domain" as const,
        }));
      case "suggest_term_definition":
        return (termsData || []).map((term) => ({
          id: term.id,
          title: term.title,
          type: "term" as const,
        }));
      default:
        return [];
    }
  };

  const getPipelineDisplayName = () => {
    return flavor.pipeline
      .replace(/_/g, " ")
      .replace(/\b\w/g, (l) => l.toUpperCase());
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

  const recordOptions = getRecordOptions();
  const isLoading = layersLoading || domainsLoading || termsLoading;

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <div className="mb-4 flex items-start gap-3">
          <Button color="gray" size="sm" onClick={onClose}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Test Pipeline Flavor: {flavor.title}
            </h2>
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {getPipelineDisplayName()} • {flavor.llm_provider}{" "}
              {flavor.llm_model}
            </div>
            <h3 className="mt-4 mb-2 text-lg font-semibold text-gray-900 dark:text-white">
              System Prompt
            </h3>
            <pre className="text-sm text-gray-500 dark:text-gray-400 whitespace-pre-wrap">
              {flavor.system_prompt}
            </pre>
            <h3 className="mt-4 mb-2 text-lg font-semibold text-gray-900 dark:text-white">
              User Prompt
            </h3>
            <pre className="text-sm text-gray-500 dark:text-gray-400 whitespace-pre-wrap">
              {flavor.user_prompt}
            </pre>
          </div>
        </div>
      </Card>

      {/* NLP Analysis Panel */}
      <Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="test-record">
              Select {getRecordTypeDisplayName()} to Test
            </Label>
            {isLoading ? (
              <div className="flex items-center gap-2 rounded-lg border p-3">
                <Spinner size="sm" />
                <span className="text-sm">
                  Loading {getRecordTypeDisplayName().toLowerCase()}s...
                </span>
              </div>
            ) : (
              <Select
                id="test-record"
                value={selectedRecord?.id || ""}
                onChange={(e) => {
                  const option = recordOptions.find(
                    (r) => r.id === e.target.value,
                  );
                  setSelectedRecord(option || null);
                }}
              >
                <option value="">
                  Select a {getRecordTypeDisplayName().toLowerCase()}...
                </option>
                {recordOptions.map((record) => (
                  <option key={record.id} value={record.id}>
                    {record.title}
                  </option>
                ))}
              </Select>
            )}
          </div>
        </div>
        {selectedRecord && (
          <>
            <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              NLP Analysis for "{selectedRecord.title}"
            </h3>
            <NlpAnalysisPanel
              text={selectedRecord.title}
              textTitle={selectedRecord.title}
              {...(selectedRecord.type === "layer" && {
                layerId: selectedRecord.id,
              })}
              {...(selectedRecord.type === "domain" && {
                domainId: selectedRecord.id,
              })}
              {...(selectedRecord.type === "term" && {
                termId: selectedRecord.id,
              })}
            />
          </>
        )}
      </Card>

      {/* Pipeline Analytics and History */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Pipeline Performance & History
          </h3>
          <div className="flex gap-2">
            <Button
              color={activeView === "analytics" ? "blue" : "gray"}
              size="sm"
              onClick={() => setActiveView("analytics")}
            >
              <BarChart3 className="mr-2 h-4 w-4" />
              Analytics
            </Button>
            <Button
              color={activeView === "history" ? "blue" : "gray"}
              size="sm"
              onClick={() => setActiveView("history")}
            >
              <Clock className="mr-2 h-4 w-4" />
              Execution History
            </Button>
          </div>
        </div>

        {activeView === "analytics" && (
          <AnalyticsDashboard
            flavorId={flavor.id}
            pipelineTypeFilter={flavor.pipeline}
            config={{
              defaultTimeRange: 30,
              showExportButton: true,
              autoRefresh: false,
            }}
            showHealthStatus={false}
          />
        )}

        {activeView === "history" && (
          <ExecutionHistory
            flavorId={flavor.id}
            config={{
              maxEntries: 25,
              autoRefresh: false,
            }}
            showFilters={true}
          />
        )}
      </Card>
    </div>
  );
};

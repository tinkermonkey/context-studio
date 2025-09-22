import React, { useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Button,
  Card,
  Select,
  Label,
  Spinner,
  Alert,
  Breadcrumb,
  Modal,
} from "flowbite-react";
import { ArrowLeft, BarChart3, Clock, Home, Edit } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { CsMainTitle } from "@/components/layout/cs_main";
import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";
import { AnalyticsDashboard } from "@/components/llm_traceability/AnalyticsDashboard";
import { ExecutionHistory } from "@/components/llm_traceability/ExecutionHistory";
import { PipelineFlavorEditor } from "@/components/llm_pipelines/PipelineFlavorEditor";
import {
  usePipelineFlavor,
  useDefaultPipelineFlavor,
} from "@/api/hooks/pipelineFlavors";
import {
  useLayerNodes,
  useDomainNodes,
  useTermNodes,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import type { PipelineType } from "@/api/services/pipelineFlavors";
import { PipelineTypes } from "@/components/llm_pipelines/pipelineTypes";

interface TestRecord {
  id: string;
  title: string;
  type: "layer" | "domain" | "term";
}

type TabType = "analytics" | "history";

export const Route = createFileRoute(
  "/app/config/pipelines/$pipelineType/test/$flavorId",
)({
  component: TestFlavorPage,
  validateSearch: (
    search: Record<string, unknown>,
  ): { tab?: TabType; recordId?: string } => {
    return {
      tab: (search.tab as TabType) || "analytics",
      recordId: search.recordId as string,
    };
  },
});

function TestFlavorPage() {
  const { pipelineType, flavorId } = Route.useParams() as {
    pipelineType: PipelineType;
    flavorId: string;
  };
  const { tab, recordId } = Route.useSearch();
  const navigate = Route.useNavigate();

  const [selectedRecord, setSelectedRecord] = useState<TestRecord | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);

  const isDefault = flavorId === "default";
  const {
    data: flavor,
    isLoading: flavorLoading,
    error: flavorError,
  } = usePipelineFlavor(isDefault ? "" : flavorId);
  const {
    data: defaultFlavor,
    isLoading: defaultFlavorLoading,
    error: defaultFlavorError,
  } = useDefaultPipelineFlavor(pipelineType);

  const currentFlavor = isDefault ? defaultFlavor : flavor;
  const currentFlavorLoading = isDefault ? defaultFlavorLoading : flavorLoading;
  const currentFlavorError = isDefault ? defaultFlavorError : flavorError;
  const { data: layersData, isLoading: layersLoading } = useLayerNodes();
  const { data: domainsData, isLoading: domainsLoading } = useDomainNodes();
  const { data: termsData, isLoading: termsLoading } = useTermNodes();

  const getRecordOptions = (): TestRecord[] => {
    if (!currentFlavor) return [];

    switch (currentFlavor.pipeline) {
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

  const recordOptions = getRecordOptions();
  const isLoading = layersLoading || domainsLoading || termsLoading;

  // Sync selectedRecord with URL recordId parameter
  useEffect(() => {
    if (recordId && recordOptions.length > 0) {
      const record = recordOptions.find((r) => r.id === recordId);
      setSelectedRecord(record || null);
    }
  }, [recordId, layersData, domainsData, termsData, currentFlavor]);

  // Function to update selected record and URL
  const handleRecordSelection = (recordId: string) => {
    const record = recordOptions.find((r) => r.id === recordId);
    setSelectedRecord(record || null);

    // Update URL with the selected record ID
    navigate({
      search: (prev) => ({ ...prev, recordId: recordId || undefined }),
      replace: true,
    });
  };

  const pipelineConfig = PipelineTypes.find((p) => p.value === pipelineType);

  const getPipelineDisplayName = () => {
    if (!currentFlavor) return "";
    return currentFlavor.pipeline
      .replace(/_/g, " ")
      .replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const getRecordTypeDisplayName = () => {
    if (!currentFlavor) return "Record";
    switch (currentFlavor.pipeline) {
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

  const setActiveTab = (newTab: TabType) => {
    navigate({
      search: { tab: newTab },
      replace: true,
    });
  };

  if (currentFlavorLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner size="lg" />
        <span className="ml-3">Loading flavor...</span>
      </div>
    );
  }

  if (currentFlavorError || !currentFlavor) {
    return (
      <Alert color="failure" className="m-4">
        <span className="font-medium">Error!</span> Unable to load flavor with
        ID: {flavorId}
      </Alert>
    );
  }

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
          <Link to="/app/config/pipelines" className="hover:text-blue-600">
            Pipeline Flavors
          </Link>
          <span>/</span>
          <Link
            to="/app/config/pipelines/$pipelineType"
            params={{ pipelineType }}
            className="hover:text-blue-600"
          >
            {pipelineConfig?.label}
          </Link>
          <span>/</span>
          <span className="text-gray-900 dark:text-white">
            Test "{currentFlavor.title}"
          </span>
        </div>
      </Breadcrumb>

      <CsMainTitle>
        <div className="flex items-center gap-3">Flavor Tester</div>
      </CsMainTitle>

      <div className="mt-6 space-y-6">
        {/* Header */}
        <Card>
          <div className="mb-4 flex items-start justify-between">
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                {currentFlavor.title}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {getPipelineDisplayName()} • {currentFlavor.llm_provider}{" "}
                {currentFlavor.llm_model}
              </p>
              <h3 className="mt-4 mb-2 text-lg font-semibold text-gray-900 dark:text-white">
                System Prompt
              </h3>
              <pre className="text-sm whitespace-pre-wrap text-gray-500 dark:text-gray-400">
                {currentFlavor.system_prompt}
              </pre>
              <h3 className="mt-4 mb-2 text-lg font-semibold text-gray-900 dark:text-white">
                User Prompt
              </h3>
              <pre className="text-sm whitespace-pre-wrap text-gray-500 dark:text-gray-400">
                {currentFlavor.user_prompt}
              </pre>
            </div>
            <div className="ml-4">
              <Button
                color="blue"
                size="sm"
                onClick={() => setShowEditModal(true)}
              >
                <Edit className="mr-2 h-4 w-4" />
                Edit Flavor
              </Button>
            </div>
          </div>
        </Card>

        {/* NLP Analysis Panel */}
        <Card>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Test Execution
          </h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
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
                    handleRecordSelection(e.target.value);
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
                flavorList={[currentFlavor.id]}
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
                color={tab === "analytics" ? "blue" : "gray"}
                size="sm"
                onClick={() => setActiveTab("analytics")}
              >
                <BarChart3 className="mr-2 h-4 w-4" />
                Analytics
              </Button>
              <Button
                color={tab === "history" ? "blue" : "gray"}
                size="sm"
                onClick={() => setActiveTab("history")}
              >
                <Clock className="mr-2 h-4 w-4" />
                Execution History
              </Button>
            </div>
          </div>

          {tab === "analytics" && (
            <AnalyticsDashboard
              flavorId={currentFlavor.id}
              pipelineTypeFilter={currentFlavor.pipeline}
              config={{
                defaultTimeRange: 30,
                showExportButton: true,
                autoRefresh: false,
              }}
              showHealthStatus={false}
            />
          )}

          {tab === "history" && (
            <ExecutionHistory
              flavorId={currentFlavor.id}
              config={{
                maxEntries: 25,
                autoRefresh: false,
              }}
              showFilters={true}
            />
          )}
        </Card>
      </div>

      {/* Edit Flavor Modal */}
      <Modal
        show={showEditModal}
        onClose={() => setShowEditModal(false)}
        size="7xl"
      >
        <div className="p-6">
          <div className="mb-4 flex items-center justify-between border-b border-gray-200 pb-4 dark:border-gray-700">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
              Edit Flavor: {currentFlavor.title}
            </h3>
          </div>
          <PipelineFlavorEditor
            pipeline={currentFlavor.pipeline}
            flavor={currentFlavor}
            onClose={() => setShowEditModal(false)}
          />
        </div>
      </Modal>
    </>
  );
}

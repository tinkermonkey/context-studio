import * as React from "react";
import { Button, Alert, Spinner } from "flowbite-react";
import { CheckCircle } from "lucide-react";
import {
  useUpdateTerm,
  useUpdateDomain,
  useUpdateLayer,
} from "@/api/hooks/structure_nodes/useStructureNodeMutations";

// Interface for the expected pipeline execution result
interface PipelineExecutionResult {
  status: "success" | "error" | "running" | "idle";
  data?: {
    // New structured format
    structured_output?: {
      definition?: string;
      reasoning?: string;
      discrepancies?: string;
      [key: string]: unknown;
    };
    response_content?: string;
    execution_id?: string;
    flavor_id?: string;
    pipeline_type?: string;
    token_usage?: { [key: string]: number };

    // Legacy format support
    definition?: string;
    reasoning?: string;
    discrepancies?: string;
  };
  error?: string;
}

interface PipelineResultViewProps {
  result: PipelineExecutionResult;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  apiContext: Record<string, any> | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  buildApiContext: () => Record<string, any>;
  termId?: string | null;
  domainId?: string | null;
  layerId?: string | null;
}

const PipelineResultView: React.FC<PipelineResultViewProps> = ({
  result,
  apiContext,
  buildApiContext,
  termId,
  domainId,
  layerId,
}) => {
  const [saveMessageLocal, setSaveMessageLocal] = React.useState<string | null>(
    null,
  );
  const [isSavingLocal, setIsSavingLocal] = React.useState(false);
  const [savedContextSnapshotLocal, setSavedContextSnapshotLocal] =
    React.useState<string | null>(null);
  const [savedVisibleLocal, setSavedVisibleLocal] = React.useState(false);

  const updateTerm = useUpdateTerm();
  const updateDomain = useUpdateDomain();
  const updateLayer = useUpdateLayer();

  const canSaveLocal = Boolean(termId || domainId || layerId);

  // Check if there's any saveable content
  const hasSaveableContent = Boolean(
    result.data?.structured_output?.definition ||
      result.data?.definition ||
      result.data?.response_content,
  );

  const currentContextSnapshotLocal = React.useMemo(() => {
    try {
      return JSON.stringify(apiContext || buildApiContext());
    } catch (_e) {  // eslint-disable-line @typescript-eslint/no-unused-vars
  
      return null;
    }
  }, [apiContext, buildApiContext]);

  const isSavedAndUnchangedLocal = Boolean(
    savedContextSnapshotLocal &&
      currentContextSnapshotLocal &&
      savedContextSnapshotLocal === currentContextSnapshotLocal,
  );

  // Hide the saved indicator when the current snapshot diverges from the saved snapshot
  React.useEffect(() => {
    if (
      savedVisibleLocal &&
      savedContextSnapshotLocal &&
      currentContextSnapshotLocal
    ) {
      if (savedContextSnapshotLocal !== currentContextSnapshotLocal) {
        setSavedVisibleLocal(false);
      }
    }
  }, [
    currentContextSnapshotLocal,
    savedContextSnapshotLocal,
    savedVisibleLocal,
  ]);

   
  const handleSaveLocal = async (res: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => {
    // Extract definition from structured_output, legacy format, or raw response
    const definition =
      res?.data?.structured_output?.definition ||
      res?.data?.definition ||
      res?.data?.response_content;
    if (!definition) return;
    setSaveMessageLocal(null);
    setIsSavingLocal(true);

   
    const payload: any   // eslint-disable-line @typescript-eslint/no-explicit-any
= { definition };
    try {
      if (termId) {
        await updateTerm.mutateAsync({ id: termId, data: payload });
        setSaveMessageLocal("Definition saved to term successfully");
      } else if (domainId) {
        await updateDomain.mutateAsync({ id: domainId, data: payload });
        setSaveMessageLocal("Definition saved to domain successfully");
      } else if (layerId) {
        await updateLayer.mutateAsync({ id: layerId, data: payload });
        setSaveMessageLocal("Definition saved to layer successfully");
      } else {
        throw new Error("No valid target ID provided for saving definition");
      }

      try {
        const snapshot = JSON.stringify(apiContext || buildApiContext());
        setSavedContextSnapshotLocal(snapshot);
        setSavedVisibleLocal(true);
      } catch (_e) {  // eslint-disable-line @typescript-eslint/no-unused-vars
  
        setSavedContextSnapshotLocal(null);
        setSavedVisibleLocal(false);
      }
      setIsSavingLocal(false);
   
    } catch (err: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 {
      setSaveMessageLocal(err?.message || "Failed to save definition");
      setIsSavingLocal(false);
    }
  };

  if (result.status === "success" && result.data) {
    const data = result.data;

    // Extract structured data, with fallback to legacy format
    const structuredData = data.structured_output || {};
    const definition = structuredData.definition || data.definition;
    const reasoning = structuredData.reasoning || data.reasoning;
    const discrepancies = structuredData.discrepancies || data.discrepancies;

    return (
      <div className="flex h-full flex-col space-y-3">
        {definition && (
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-800">
            <h5 className="mb-2 font-medium text-gray-900 dark:text-white">
              Definition
            </h5>
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {definition}
            </p>
          </div>
        )}

        {/* Fallback: Show raw response if no structured definition found */}
        {!definition && data.response_content && (
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-800">
            <h5 className="mb-2 font-medium text-gray-900 dark:text-white">
              Response
            </h5>
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {data.response_content}
            </p>
          </div>
        )}

        {reasoning && (
          <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
            <h5 className="mb-2 font-medium text-blue-900 dark:text-blue-200">
              Reasoning
            </h5>
            <p className="text-sm text-blue-700 dark:text-blue-300">
              {reasoning}
            </p>
          </div>
        )}

        {discrepancies && (
          <div className="rounded-lg bg-yellow-50 p-3 dark:bg-yellow-900/20">
            <h5 className="mb-2 font-medium text-yellow-900 dark:text-yellow-200">
              Discrepancies
            </h5>
            <p className="text-sm text-yellow-700 dark:text-yellow-300">
              {discrepancies}
            </p>
          </div>
        )}

        <div className="flex flex-1 items-end p-2">
          <div className="flex items-center gap-2">
            <Button
              size="xs"
              onClick={() => handleSaveLocal(result)}
              disabled={
                isSavingLocal ||
                !canSaveLocal ||
                !hasSaveableContent ||
                savedVisibleLocal
              }
              title={
                isSavingLocal
                  ? "Saving..."
                  : !canSaveLocal
                    ? "No context ID provided for saving"
                    : !hasSaveableContent
                      ? "No content available to save"
                      : "Save this definition to the selected target"
              }
            >
              {isSavingLocal ? (
                <span className="flex items-center gap-2">
                  <Spinner size="sm" /> Saving
                </span>
              ) : (
                "Use This Definition"
              )}
            </Button>

            {savedVisibleLocal && isSavedAndUnchangedLocal && (
              <div className="flex items-center text-sm text-green-700">
                <CheckCircle className="mr-1 h-4 w-4" />
                <span>Saved</span>
              </div>
            )}
          </div>
        </div>

        {saveMessageLocal && (
          <div
            className={`text-xs ${saveMessageLocal.includes("successfully") ? "text-green-700" : "text-red-700"}`}
          >
            {saveMessageLocal}
          </div>
        )}
      </div>
    );
  }

  if (result.status === "error") {
    return (
      <Alert color="failure">
        <div>
          <h5 className="mb-1 font-medium">Execution Error</h5>
          <p className="text-sm">{result.error}</p>
        </div>
      </Alert>
    );
  }

  return (
    <div className="flex items-center justify-center p-8 text-gray-500 dark:text-gray-400">
      {result.status === "running"
        ? "Executing pipeline..."
        : "Waiting to execute..."}
    </div>
  );
};

export default PipelineResultView;

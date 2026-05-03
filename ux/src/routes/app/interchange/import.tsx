/**
 * Interchange Import Page
 *
 * Page for importing ontology data with conflict resolution
 */

import React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CsMainTitle } from "@/components/layout/cs_main";
import { ImportPanel } from "@/components/interchange/ImportPanel";
import { ConflictResolutionModal } from "@/components/interchange/ConflictResolutionModal";
import { useInterchangeImport } from "@/api/hooks/interchange";
import { useButterToast } from "@/hooks/useButterToast";
import { ResolutionRecord, ImportPlanResponse } from "@/api/types/interchange";
import { useNavigate } from "@tanstack/react-router";

export const Route = createFileRoute("/app/interchange/import")({
  component: ImportComponent,
});

function ImportComponent() {
  const { error, success } = useButterToast();
  const navigate = useNavigate();

  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [selectedFormat, setSelectedFormat] = React.useState<string>("auto");
  const [showConflictModal, setShowConflictModal] = React.useState(false);
  const [importPlan, setImportPlan] = React.useState<ImportPlanResponse | null>(
    null
  );

  // Dry-run mutation (preview)
  const dryRunMutation = useInterchangeImport({
    onSuccess: (response) => {
      if ("conflicts" in response) {
        // This is an ImportPlanResponse from dry_run
        setImportPlan(response as ImportPlanResponse);
        setShowConflictModal(true);
        success(`Found ${(response as ImportPlanResponse).conflicts.length} conflicts`);
      }
    },
    onError: (err) => {
      error(
        `Import preview failed: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    },
  });

  // Commit mutation (actual import)
  const commitMutation = useInterchangeImport({
    onSuccess: (response) => {
      if ("id" in response) {
        const run = response;
        setShowConflictModal(false);
        success(`Import committed successfully (Run: ${run.id})`);
        // Navigate to the new run's detail page
        navigate({ to: `/app/interchange/runs/${run.id}` });
      }
    },
    onError: (err) => {
      error(
        `Import commit failed: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    },
  });

  const handlePreviewRequested = (file: File, format: string) => {
    setSelectedFile(file);
    setSelectedFormat(format);

    // Trigger dry-run
    dryRunMutation.mutate({
      format,
      file,
      dry_run: true,
    });
  };

  const handleConflictResolve = (resolutions: ResolutionRecord[]) => {
    if (!selectedFile || !selectedFormat) {
      error("File or format lost");
      return;
    }

    // Commit with resolutions
    commitMutation.mutate({
      format: selectedFormat,
      file: selectedFile,
      dry_run: false,
      resolutions,
    });
  };

  return (
    <>
      <CsMainTitle>Import Ontology</CsMainTitle>
      <div className="mt-6">
        <ImportPanel onPreviewRequested={handlePreviewRequested} />
      </div>

      <ConflictResolutionModal
        isOpen={showConflictModal}
        onClose={() => setShowConflictModal(false)}
        conflicts={importPlan?.conflicts || []}
        newEntityCount={importPlan?.new_entity_count || 0}
        onCommit={handleConflictResolve}
        isLoading={commitMutation.isPending}
      />
    </>
  );
}

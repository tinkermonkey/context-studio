import { useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { Drawer } from "@/components/ui/Drawer";
import { useToasts } from "@/components/ui/Toast";
import { useDemoDatasets, useLoadDemoDataset } from "@/api/hooks/admin/useDemoDataset";

export interface DemoDatasetPickerProps {
  open: boolean;
  onClose: () => void;
}

interface InlineError {
  name: string;
  message: string;
}

export function DemoDatasetPicker({ open, onClose }: DemoDatasetPickerProps) {
  const { data: datasets, isLoading, error } = useDemoDatasets();
  const loadMutation = useLoadDemoDataset();
  const { toast } = useToasts();
  const [inlineError, setInlineError] = useState<InlineError | null>(null);
  const [pendingName, setPendingName] = useState<string | null>(null);

  const handleLoad = (name: string) => {
    setInlineError(null);
    setPendingName(name);
    loadMutation.mutate(name, {
      onSuccess: (result) => {
        setPendingName(null);
        toast(
          "success",
          "Demo dataset loaded",
          `${result.taxonomies} taxonomy · ${result.concept_schemes} schemes · ${result.classes} classes`,
        );
        onClose();
      },
      onError: (err: unknown) => {
        setPendingName(null);
        // ApiError normalizes status into `status` and message; treat 409 as already-loaded
        const apiError = err as { status?: number; message?: string };
        if (apiError.status === 409) {
          setInlineError({
            name,
            message: apiError.message || "This demo dataset is already loaded.",
          });
        } else {
          toast(
            "error",
            "Failed to load demo dataset",
            apiError.message || "An unexpected error occurred.",
          );
        }
      },
    });
  };

  return (
    <Drawer open={open} onClose={onClose} title="Load Demo Dataset">
      <div className="demo-dataset-picker" data-testid="demo-dataset-picker">
        {isLoading && (
          <div className="empty-state compact" data-testid="demo-dataset-loading">
            <div className="empty-state-content">
              <div className="empty-state-title">Loading available datasets…</div>
            </div>
          </div>
        )}

        {error && (
          <div className="empty-state compact" data-testid="demo-dataset-error">
            <div className="empty-state-content">
              <div className="empty-state-title">Failed to load demo datasets</div>
              <div className="empty-state-description">{(error as Error).message}</div>
            </div>
          </div>
        )}

        {datasets && datasets.length === 0 && (
          <div className="empty-state compact">
            <div className="empty-state-content">
              <div className="empty-state-title">No demo datasets available</div>
            </div>
          </div>
        )}

        {datasets &&
          datasets.map((dataset) => {
            const isPending = pendingName === dataset.name && loadMutation.isPending;
            const conflict = inlineError && inlineError.name === dataset.name;
            return (
              <article
                key={dataset.name}
                className="demo-dataset-card"
                data-testid={`demo-dataset-card-${dataset.name}`}
              >
                <header className="demo-dataset-card-head">
                  <h3 className="demo-dataset-card-title">{dataset.title}</h3>
                  <span
                    className="demo-dataset-card-meta"
                    data-testid={`demo-dataset-meta-${dataset.name}`}
                  >
                    {dataset.paper_count} papers · {dataset.taxonomy_count} taxonomy ·{" "}
                    {dataset.class_count} classes
                  </span>
                </header>
                <p className="demo-dataset-card-description">{dataset.description}</p>
                {conflict && (
                  <div
                    className="demo-dataset-card-error"
                    role="alert"
                    data-testid={`demo-dataset-error-${dataset.name}`}
                  >
                    {inlineError?.message}
                  </div>
                )}
                <div className="demo-dataset-card-actions">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleLoad(dataset.name)}
                    disabled={isPending || loadMutation.isPending}
                    data-testid={`demo-dataset-load-${dataset.name}`}
                  >
                    {isPending ? "Loading…" : "Load"}
                  </Button>
                </div>
              </article>
            );
          })}
      </div>
    </Drawer>
  );
}

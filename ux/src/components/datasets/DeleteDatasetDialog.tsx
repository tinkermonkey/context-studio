import { ConfirmDialog } from "@tinkermonkey/heimdall-ui";
import { datasetsCopy } from "./copy";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

function plural(n: number, singular: string, pluralForm: string): string {
  return `${n} ${n === 1 ? singular : pluralForm}`;
}

interface DeleteDatasetDialogProps {
  dataset: DatasetResponse | null;
  taxonomyTitle?: string;
  onClose: () => void;
  onConfirm: (dataset: DatasetResponse) => void;
}

/**
 * Confirms deleting a dataset, saying what goes with it: its individuals and
 * their relationships. A direct action, not a proposal; each removal is recorded.
 */
export function DeleteDatasetDialog({
  dataset,
  taxonomyTitle,
  onClose,
  onConfirm,
}: DeleteDatasetDialogProps) {
  return (
    <ConfirmDialog
      isOpen={dataset !== null}
      onClose={onClose}
      onConfirm={() => dataset && onConfirm(dataset)}
      title={datasetsCopy.delete.title}
      subtitle={
        dataset ? `${taxonomyTitle ? `${taxonomyTitle} · ` : ""}${dataset.identifier}` : undefined
      }
      confirmLabel={datasetsCopy.delete.confirm}
      cancelLabel={datasetsCopy.delete.cancel}
      message={
        dataset && (
          <div className="stack" data-testid="dataset-delete-summary">
            <p>
              Delete <strong>{dataset.title}</strong> with its{" "}
              <strong>{plural(dataset.individual_count, "individual", "individuals")}</strong> and{" "}
              <strong>{plural(dataset.relationship_count, "relationship", "relationships")}</strong>
              ?
            </p>
            <p className="entity-note">
              The schema stays. Each removed individual and relationship is recorded in the change
              history.
            </p>
          </div>
        )
      }
    />
  );
}

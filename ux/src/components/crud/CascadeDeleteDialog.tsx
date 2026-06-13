import { Modal, Button, FormCallout } from "@tinkermonkey/heimdall-ui";
import { pluralize } from "./utils";

export interface CascadeImpactData {
  totalCount: number;
  stats: Array<{ label: string; count: number }>;
  items: Array<{ type: string; label: string; id: string }>;
}

interface CascadeDeleteDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  target?: { id: string; label: string };
  ids?: string[];
  entityType: string;
  impactData?: CascadeImpactData;
  isDeleting?: boolean;
  isFetching?: boolean;
}

function getDialogTitle(
  target?: { label: string },
  ids?: string[],
  entityType?: string,
): string {
  if (ids && ids.length > 1) {
    return `Delete ${ids.length} ${pluralize(entityType ?? "item", ids.length)}?`;
  }
  if (target) return `Delete "${target.label}"?`;
  return "Delete?";
}

export function CascadeDeleteDialog({
  isOpen,
  onClose,
  onConfirm,
  target,
  ids,
  entityType,
  impactData,
  isDeleting = false,
  isFetching = false,
}: CascadeDeleteDialogProps) {
  const isBulk = ids && ids.length > 1;
  const title = getDialogTitle(target, ids, entityType);
  const hasImpact = (impactData?.totalCount ?? 0) > 0;
  const dependentCount = impactData?.totalCount ?? 0;

  const deleteLabel = hasImpact
    ? `Delete (+ ${dependentCount} dependent${dependentCount !== 1 ? "s" : ""})`
    : "Delete";

  const displayedItems = impactData?.items.slice(0, 60) ?? [];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="md"
      data-testid="cascade-delete-dialog"
      footer={
        <div className="form-actions">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={isDeleting}
            data-testid="cascade-delete-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={onConfirm}
            disabled={isDeleting || isFetching}
            data-testid="cascade-delete-confirm"
          >
            {isDeleting ? "Deleting…" : deleteLabel}
          </Button>
        </div>
      }
    >
      <div className="ce-cascade" data-testid="cascade-delete-content">
        {isFetching ? (
          <FormCallout variant="info" icon="info">
            Checking for dependent items…
          </FormCallout>
        ) : !hasImpact ? (
          <FormCallout variant="info" icon="check">
            {impactData
              ? "Safe to remove — no dependent items will be affected."
              : "This action cannot be undone."}
          </FormCallout>
        ) : (
          <>
            <FormCallout variant="warn" icon="alert">
              {isBulk
                ? `Deleting ${ids!.length} ${pluralize(entityType, ids!.length)} will also remove ${dependentCount} dependent item${dependentCount !== 1 ? "s" : ""}.`
                : `Deleting this ${entityType.toLowerCase()} will also remove ${dependentCount} dependent item${dependentCount !== 1 ? "s" : ""}.`}
            </FormCallout>

            <div className="ce-cascade__summary" data-testid="cascade-impact-summary">
              {impactData!.stats.map((stat) => (
                <div key={stat.label} className="ce-cascade__stat">
                  <span className="ce-cascade__num">{stat.count}</span>
                  <span className="ce-cascade__kind">{stat.label}</span>
                </div>
              ))}
            </div>

            {displayedItems.length > 0 && (
              <div className="ce-cascade__list" data-testid="cascade-impact-items">
                {displayedItems.map((item, index) => (
                  <div key={index} className="ce-cascade__item">
                    <span className="ce-cascade__type">{item.type}</span>
                    <span>{item.label}</span>
                    <span className="ce-cascade__item-id">{item.id}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

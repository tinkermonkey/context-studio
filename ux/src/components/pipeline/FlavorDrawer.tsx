import { Button } from "@/components/ui/Button";
import type { components } from "@/api/types";

type PipelineFlavorResponse = components["schemas"]["PipelineFlavorResponse"];

interface FlavorDrawerProps {
  flavor: PipelineFlavorResponse;
  onClose: () => void;
  onDelete: (id: string) => Promise<void>;
  isDeleting?: boolean;
}

export function FlavorDrawer({
  flavor,
  onClose,
  onDelete,
  isDeleting = false,
}: FlavorDrawerProps) {
  const handleDelete = async () => {
    if (!window.confirm("Are you sure you want to delete this flavor?")) {
      return;
    }
    try {
      await onDelete(flavor.id);
      onClose();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete flavor");
    }
  };

  return (
    <div
      data-testid="flavor-drawer"
      style={{
        padding: "var(--space-6)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-6)",
        height: "100%",
      }}
    >
      <div>
        <h3 style={{ margin: 0, marginBottom: "var(--space-2)" }}>{flavor.name}</h3>
        <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--color-text-secondary)" }}>
          {flavor.description}
        </p>
      </div>

      <div style={{ backgroundColor: "var(--color-bg-secondary)", padding: "var(--space-4)" }}>
        <div style={{ marginBottom: "var(--space-3)" }}>
          <label style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-secondary)" }}>
            ID
          </label>
          <p
            style={{
              margin: "var(--space-1) 0 0",
              fontFamily: "monospace",
              fontSize: "0.875rem",
              wordBreak: "break-all",
            }}
            data-testid="flavor-drawer-id"
          >
            {flavor.id}
          </p>
        </div>

        <div style={{ marginBottom: "var(--space-3)" }}>
          <label style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-secondary)" }}>
            Steps
          </label>
          <p style={{ margin: "var(--space-1) 0 0", fontFamily: "monospace", fontSize: "0.875rem" }} data-testid="flavor-drawer-step-count">
            {flavor.step_count} step{flavor.step_count !== 1 ? "s" : ""}
          </p>
        </div>

        <div>
          <label style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--color-text-secondary)" }}>
            Created
          </label>
          <p style={{ margin: "var(--space-1) 0 0", fontSize: "0.875rem" }}>
            {new Date(flavor.created_at).toLocaleDateString()}
          </p>
        </div>
      </div>

      <div style={{ marginTop: "auto", display: "flex", gap: "var(--space-2)" }}>
        <Button
          variant="danger"
          onClick={handleDelete}
          disabled={isDeleting}
          data-testid="flavor-drawer-delete-button"
        >
          {isDeleting ? "Deleting..." : "Delete"}
        </Button>
        <Button variant="ghost" onClick={onClose} style={{ marginLeft: "auto" }}>
          Close
        </Button>
      </div>
    </div>
  );
}

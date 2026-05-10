import { useState, useEffect, useRef } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Textarea, Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useToasts } from "@/components/ui/Toast";
import { useAutosave } from "@/hooks/useAutosave";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import { formatTimeAgo } from "@/utils/dateFormatting";
import { useTaxonomy, useUpdateTaxonomy, useDeleteTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { TaxonomyPublishDialog } from "@/components/ontology/TaxonomyPublishDialog";
import { taxonomiesCopy } from "./taxonomies/-copy";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];

function TaxonomyDetailContent({ taxonomy }: { taxonomy: TaxonomyResponse }) {
  const [title, setTitle] = useState(taxonomy?.title ?? "");
  const [description, setDescription] = useState(taxonomy?.description ?? "");
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const lastSavedAtRef = useRef<Date | null>(null);
  const navigate = useNavigate();

  const { toast } = useToasts();
  const updateMutation = useUpdateTaxonomy();
  const deleteMutation = useDeleteTaxonomy();
  const { data: schemesResponse } = useSchemes(taxonomy.id);
  const schemes = schemesResponse?.items || [];

  const { performDelete, undo } = useUndoDelete({
    onDelete: (id: string) => deleteMutation.mutateAsync(id),
    onDeleteError: (id: string, error: Error) => {
      toast("error", `Failed to delete taxonomy: ${error.message}`);
    },
    undoWindowMs: 8000,
  });

  useEffect(() => {
    setTitle(taxonomy?.title ?? "");
    setDescription(taxonomy?.description ?? "");
    lastSavedAtRef.current = null;
  }, [taxonomy]);

  const isDirty = title !== taxonomy?.title || description !== taxonomy?.description;

  const updateData = {
    title,
    description,
  };

  const { status } = useAutosave({
    data: updateData,
    mutationFn: async () => {
      if (!taxonomy || !isDirty) return;
      await updateMutation.mutateAsync({
        id: taxonomy.id,
        data: {
          title,
          description: description || null,
        },
      });
      lastSavedAtRef.current = new Date();
    },
    onError: (error) => {
      toast("error", `Autosave failed: ${error.message}`);
    },
  });

  const autosaveState: "saving" | "saved" | "error" | undefined = status === "idle" ? undefined : (status as "saving" | "saved" | "error");

  const handlePublish = async () => {
    toast("success", taxonomiesCopy.publish.successToast(taxonomy.title, taxonomy.version + 1));
  };

  const handleDelete = async () => {
    await performDelete(taxonomy.id);
    toast("success", taxonomiesCopy.delete.successToast, "Undo", {
      action: {
        label: "Undo",
        onAction: undo,
      },
      autoDismissMs: 8000,
    });
    navigate({ to: "/app/schema/taxonomies" });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>{taxonomy.title}</h1>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          {taxonomy.status === "draft" && (
            <Button
              variant="primary"
              onClick={() => setShowPublishDialog(true)}
              data-testid="taxonomy-detail-publish-button"
            >
              Publish…
            </Button>
          )}
          <Button
            variant="danger"
            onClick={() => setShowDeleteConfirm(true)}
            data-testid="taxonomy-detail-delete-button"
          >
            Delete
          </Button>
        </div>
      </div>

      <div style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
        <div
          style={{
            backgroundColor: taxonomy.status === "draft" ? "var(--amber-100, #fef3c7)" : "var(--green-100, #dcfce7)",
            color: taxonomy.status === "draft" ? "var(--amber-800, #78350f)" : "var(--green-800, #166534)",
            padding: "4px 8px",
            borderRadius: "4px",
            fontSize: "var(--text-xs)",
            fontWeight: 500,
            textTransform: "capitalize",
          }}
        >
          {taxonomy.status}
        </div>
        <div style={{ color: "var(--canvas-fg-3)", fontSize: "var(--text-xs)" }}>
          v{taxonomy.version}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            ID
          </label>
          <Input
            type="text"
            value={taxonomy.id}
            disabled
            mono
            data-testid="taxonomy-detail-id"
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Title
          </label>
          <Input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            data-testid="taxonomy-detail-title-input"
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Description
          </label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="taxonomy-detail-description-input"
            rows={4}
          />
        </div>

        {autosaveState && (
          <div style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}>
            {autosaveState === "saving" && "Saving…"}
            {autosaveState === "saved" && lastSavedAtRef.current && `Saved ${formatTimeAgo(lastSavedAtRef.current)}`}
            {autosaveState === "error" && "Save failed"}
          </div>
        )}
      </div>

      <div style={{ borderTop: "1px solid var(--canvas-fg-4)", paddingTop: "var(--space-4)" }}>
        <h2 style={{ fontSize: "var(--text-lg)", marginBottom: "var(--space-2)" }}>Concept Schemes ({schemes.length})</h2>
        {schemes.length === 0 ? (
          <EmptyState
            title="No concept schemes"
            description="Create a concept scheme to organize classes within this taxonomy."
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {schemes.map((scheme: ConceptSchemeResponse) => (
              <div
                key={scheme.id}
                style={{
                  padding: "var(--space-3)",
                  border: "1px solid var(--canvas-fg-4)",
                  borderRadius: "4px",
                }}
              >
                <div style={{ fontWeight: 500 }}>{scheme.title}</div>
                {scheme.description && (
                  <div style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg-2)", marginTop: "4px" }}>
                    {scheme.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <TaxonomyPublishDialog
        open={showPublishDialog}
        onClose={() => setShowPublishDialog(false)}
        taxonomy={taxonomy}
        onPublish={handlePublish}
      />

      <ConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={taxonomiesCopy.delete.confirmTitle}
        message="This taxonomy and all its concept schemes will be permanently deleted."
        confirmLabel={taxonomiesCopy.delete.confirmButton}
        onConfirm={handleDelete}
        danger
        isLoading={deleteMutation.isPending}
        data-testid="taxonomy-detail-delete-confirm"
      />
    </div>
  );
}

interface RouteParams {
  taxonomyId: string;
}

function TaxonomyDetailPage() {
  const { taxonomyId } = Route.useParams() as RouteParams;
  const { data: taxonomy, isLoading, error, refetch } = useTaxonomy(taxonomyId);

  if (isLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <Skeleton height={32} width={200} />
        <Skeleton height={40} />
        <Skeleton height={100} />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} height={40} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message="Failed to load taxonomy"
        />
      </div>
    );
  }

  if (!taxonomy) {
    return (
      <EmptyState
        title="Taxonomy not found"
        description="The taxonomy you're looking for doesn't exist."
      />
    );
  }

  return <TaxonomyDetailContent taxonomy={taxonomy} />;
}

export const Route = createFileRoute("/app/schema/taxonomies/$taxonomyId")({
  component: TaxonomyDetailPage,
});

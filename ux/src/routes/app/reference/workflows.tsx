import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button, Modal, Chip, RowMenu, FilterBar, PageHeader } from "@tinkermonkey/heimdall-ui";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { GroundingWorkflowDrawer } from "@/components/reference/GroundingWorkflowDrawer";
import { GroundingWorkflowForm } from "@/components/reference/GroundingWorkflowForm";
import { useToasts } from "@/components/ui/Toast";
import { formatRelativeTime } from "@/utils/formatters";
import { COPY } from "./copy";
import {
  useGroundingWorkflows,
  useCreateGroundingWorkflow,
  useDeleteGroundingWorkflow,
  useRunGroundingWorkflow,
} from "@/api/hooks/reference";
import type {
  GroundingWorkflowResponse,
  GroundingWorkflowCreate,
} from "@/api/types/manual/grounding";

interface WorkflowsSearchParams {
  selected?: string;
}

interface WorkflowsPageContentProps {
  selectedId?: string;
  onSelectedIdChange: (id: string | undefined) => void;
  onCreateClick: () => void;
  onDeleteClick: (id: string) => void;
  onRunClick: (id: string) => void;
}

export function WorkflowsPageContent({
  selectedId,
  onSelectedIdChange,
  onCreateClick,
  onDeleteClick,
  onRunClick,
}: WorkflowsPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");
  const { data: workflows, isLoading, error, refetch } = useGroundingWorkflows();

  const filteredData = (workflows || []).filter((workflow: GroundingWorkflowResponse) =>
    workflow.title.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const workflowColumns: Column<GroundingWorkflowResponse>[] = [
    {
      key: "title",
      label: COPY.workflowsTableHeaderName,
      sortable: true,
      render: (value, row) => (
        <button
          style={{
            background: "none",
            border: "none",
            color: "var(--accent-cyan, #22d3ee)",
            fontWeight: 500,
            cursor: "pointer",
            padding: 0,
          }}
          onClick={() => onSelectedIdChange(row.id)}
          data-testid={`workflow-name-${row.id}`}
        >
          {value as string}
        </button>
      ),
    },
    {
      key: "source",
      label: COPY.workflowsTableHeaderSource,
      render: (value) => <Chip variant="cyan">{value as string}</Chip>,
    },
    {
      key: "class_scope",
      label: COPY.workflowsTableHeaderClassScope,
      render: (value) => {
        const scopes = value as string[];
        return (
          <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap" }}>
            {scopes.length > 0 ? (
              scopes.slice(0, 2).map((scope) => (
                <Chip key={scope} variant="violet">
                  {scope}
                </Chip>
              ))
            ) : (
              <span className="opacity-60">—</span>
            )}
            {scopes.length > 2 && (
              <span className="opacity-60" style={{ fontSize: "var(--text-xs)" }}>
                +{scopes.length - 2}
              </span>
            )}
          </div>
        );
      },
    },
    {
      key: "status",
      label: COPY.workflowsTableHeaderStatus,
      render: (value) => {
        const status = value as string;
        const statusColor = status === "active" ? "emerald" : status === "error" ? "rose" : "neutral";
        return <Chip variant={statusColor as "emerald" | "rose" | "neutral"}>{status}</Chip>;
      },
    },
    {
      key: "last_run",
      label: COPY.workflowsTableHeaderLastRun,
      render: (value) => {
        const date = value as string | null;
        return (
          <span className="opacity-60" style={{ fontSize: "var(--text-xs)" }}>
            {date ? formatRelativeTime(date) : "—"}
          </span>
        );
      },
    },
    {
      key: "id",
      label: "",
      width: "40px",
      render: (_, row) => (
        <RowMenu
          data-testid={`workflow-row-actions-${row.id}`}
          actions={[
            { id: "view", label: "View details", icon: "edit" },
            { id: "run", label: "Run now" },
            { type: "separator" },
            { id: "delete", label: "Delete", icon: "trash", danger: true },
          ]}
          onAction={(actionId: string) => {
            if (actionId === "view") onSelectedIdChange(row.id);
            if (actionId === "run") onRunClick(row.id);
            if (actionId === "delete") onDeleteClick(row.id);
          }}
        />
      ),
    },
  ];

  if (isLoading) {
    return (
      <div data-testid="reference-workflows-page" className="stack">
        <div className="skeleton" style={{ height: 32, width: 200 }} />
        <div className="skeleton" style={{ height: 40 }} />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 40 }} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="reference-workflows-page" className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message={COPY.failedToLoadGroundingWorkflows}
        />
      </div>
    );
  }

  if ((workflows || []).length === 0) {
    return (
      <div data-testid="reference-workflows-page">
        <EmptyState
          title={COPY.workflowsEmptyStateTitle}
          description={COPY.workflowsEmptyStateDescription}
          action={{
            label: COPY.newWorkflowButton,
            onClick: onCreateClick,
          }}
        />
      </div>
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = (workflows || []).length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="reference-workflows-page">
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search workflows…"
        showingCount={filteredData.length}
        totalCount={(workflows || []).length}
      />

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={COPY.workflowsFilteredEmptyTitle}
            description={COPY.workflowsFilteredEmptyDescription}
          />
        </div>
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderInspectorContent={(workflow) => (
            <GroundingWorkflowDrawer
              key={workflow.id}
              workflowId={workflow.id}
              onClose={() => onSelectedIdChange(undefined)}
            />
          )}
        >
          <SchemaTable
            columns={workflowColumns}
            data={filteredData}
            onRowSelect={(id) => onSelectedIdChange(id)}
            selectedId={selectedId}
            tableTestId="reference-workflows-table"
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

export function WorkflowsPageWrapper() {
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/reference/workflows" });
  const selectedId = searchParams.selected;
  const [showCreateModal, setShowCreateModal] = useState(false);
  const createMutation = useCreateGroundingWorkflow();
  const deleteMutation = useDeleteGroundingWorkflow();
  const runMutation = useRunGroundingWorkflow();
  const { toast } = useToasts();

  const handleSelectedIdChange = (id: string | undefined) => {
    navigate({
      to: "/app/reference/workflows",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSubmit = async (data: GroundingWorkflowCreate) => {
    try {
      const result = await createMutation.mutateAsync(data);
      setShowCreateModal(false);
      handleSelectedIdChange(result.id);
      toast("success", COPY.workflowCreatedSuccess);
    } catch (error) {
      toast("error", error instanceof Error ? error.message : COPY.workflowCreateError);
    }
  };

  const handleDeleteClick = (id: string) => {
    if (confirm("Delete this workflow? This action cannot be undone.")) {
      deleteMutation
        .mutateAsync(id)
        .then(() => {
          if (selectedId === id) handleSelectedIdChange(undefined);
          toast("success", "Workflow deleted.");
        })
        .catch((error) => {
          toast("error", error instanceof Error ? error.message : "Failed to delete workflow.");
        });
    }
  };

  const handleRunClick = (id: string) => {
    runMutation
      .mutateAsync(id)
      .then(() => toast("success", "Workflow run started."))
      .catch((error) => {
        toast("error", error instanceof Error ? error.message : "Failed to run workflow.");
      });
  };

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Reference"
        title={COPY.workflowsPageTitle}
        idChip="/reference/workflows"
        actions={
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="new-workflow-button"
          >
            <Plus size={16} style={{ marginRight: "var(--space-1)" }} />
            {COPY.newWorkflowButton}
          </Button>
        }
      />

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={COPY.createWorkflowModalTitle}
        data-testid="workflow-create-modal"
      >
        <div style={{ padding: "var(--space-4)" }}>
          <GroundingWorkflowForm
            onSubmit={handleCreateSubmit}
            isLoading={createMutation.isPending}
          />
        </div>
      </Modal>

      <div data-testid="workflows-content">
        <WorkflowsPageContent
          selectedId={selectedId}
          onSelectedIdChange={handleSelectedIdChange}
          onCreateClick={() => setShowCreateModal(true)}
          onDeleteClick={handleDeleteClick}
          onRunClick={handleRunClick}
        />
      </div>
    </div>
  );
}

export function WorkflowsPage() {
  return <WorkflowsPageWrapper />;
}

export const Route = createFileRoute("/app/reference/workflows")({
  component: WorkflowsPage,
  validateSearch: (search: Record<string, unknown>): WorkflowsSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});

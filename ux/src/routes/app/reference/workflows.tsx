import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical, Plus } from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Modal } from "@/components/ui/Modal";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { GroundingWorkflowDrawer } from "@/components/reference/GroundingWorkflowDrawer";
import { GroundingWorkflowForm } from "@/components/reference/GroundingWorkflowForm";
import { useToasts } from "@/components/ui/Toast";
import { formatRelativeTime } from "@/utils/formatters";
import { COPY } from "./copy";
import { useGroundingWorkflows, useCreateGroundingWorkflow } from "@/api/hooks/reference";
import type { GroundingWorkflowResponse, GroundingWorkflowCreate } from "@/api/types/manual/grounding";

interface WorkflowsSearchParams {
  selected?: string;
}

interface WorkflowsPageContentProps {
  selectedId?: string;
  onSelectedIdChange: (id: string | undefined) => void;
  onCreateClick: () => void;
}

function WorkflowsPageContent({
  selectedId,
  onSelectedIdChange,
  onCreateClick,
}: WorkflowsPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");
  const { data: workflows, isLoading, error, refetch } = useGroundingWorkflows();

  const filteredData = (workflows || []).filter((workflow: GroundingWorkflowResponse) =>
    workflow.title.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const workflowColumns: ColumnDef<GroundingWorkflowResponse>[] = [
    {
      accessorKey: "title",
      header: COPY.workflowsTableHeaderName,
      cell: (info) => {
        const workflowId = info.row.original.id;
        return (
          <button
            style={{
              background: "none",
              border: "none",
              color: "var(--cyan-600, #0891b2)",
              fontWeight: 500,
              cursor: "pointer",
              padding: 0,
            }}
            onClick={() => onSelectedIdChange(workflowId)}
            data-testid={`workflow-name-${workflowId}`}
          >
            {info.getValue() as string}
          </button>
        );
      },
    },
    {
      accessorKey: "source",
      header: COPY.workflowsTableHeaderSource,
      cell: (info) => <Chip color="cyan">{info.getValue() as string}</Chip>,
    },
    {
      accessorKey: "class_scope",
      header: COPY.workflowsTableHeaderClassScope,
      cell: (info) => {
        const scopes = info.getValue() as string[];
        return (
          <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap" }}>
            {scopes.length > 0 ? (
              scopes.slice(0, 2).map((scope) => (
                <Chip key={scope} color="violet">
                  {scope}
                </Chip>
              ))
            ) : (
              <span className="muted-text">—</span>
            )}
            {scopes.length > 2 && (
              <span className="muted-text" style={{ fontSize: "var(--text-xs)" }}>
                +{scopes.length - 2}
              </span>
            )}
          </div>
        );
      },
    },
    {
      accessorKey: "status",
      header: COPY.workflowsTableHeaderStatus,
      cell: (info) => {
        const status = info.getValue() as string;
        const statusColor = status === "active" ? "emerald" : status === "error" ? "rose" : "gray";

        return <Chip color={statusColor}>{status}</Chip>;
      },
    },
    {
      accessorKey: "last_run",
      header: COPY.workflowsTableHeaderLastRun,
      cell: (info) => {
        const date = info.getValue() as string | null;
        return (
          <span className="muted-text" style={{ fontSize: "var(--text-xs)" }}>
            {date ? formatRelativeTime(date) : "—"}
          </span>
        );
      },
    },
  ];

  const renderRowActions = (workflow: GroundingWorkflowResponse) => (
    <button
      onClick={() => onSelectedIdChange(workflow.id)}
      aria-label="Actions"
      data-testid={`workflow-row-actions-${workflow.id}`}
      className="btn btn-icon"
    >
      <MoreVertical size={16} style={{ color: "var(--canvas-fg-3)" }} />
    </button>
  );

  if (isLoading) {
    return (
      <div data-testid="reference-workflows-page" className="stack">
        <Skeleton height={32} width={200} />
        <Skeleton height={40} />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} height={40} />
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
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

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
          renderDrawerContent={(workflow) => (
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
            renderRowActions={renderRowActions}
            selectedId={selectedId}
            tableTestId="reference-workflows-table"
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

function WorkflowsPageWrapper() {
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/reference/workflows" });
  const selectedId = searchParams.selected;
  const [showCreateModal, setShowCreateModal] = useState(false);
  const createMutation = useCreateGroundingWorkflow();
  const { toast } = useToasts();

  const handleSelectedIdChange = (id: string | undefined) => {
    navigate({
      to: "/app/reference/workflows",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateClick = () => {
    setShowCreateModal(true);
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

  return (
    <div className="stack">
      <div className="flex-between">
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>{COPY.workflowsPageTitle}</h1>
        <Button variant="primary" onClick={handleCreateClick} data-testid="new-workflow-button">
          <Plus size={16} style={{ marginRight: "var(--space-1)" }} />
          {COPY.newWorkflowButton}
        </Button>
      </div>

      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={COPY.createWorkflowModalTitle}
        size="md"
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
          onCreateClick={handleCreateClick}
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

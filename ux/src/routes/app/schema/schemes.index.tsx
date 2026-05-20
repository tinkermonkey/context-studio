import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";
import { useToasts } from "@/components/ui/Toast";
import { Button } from "@tinkermonkey/heimdall-ui";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { SchemeForm } from "@/components/schema/SchemeForm";
import { SchemeDrawer } from "@/components/ontology/SchemeDrawer";
import { useSchemes, useCreateScheme } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { schemesCopy } from "./schemes/-copy";
import type { components } from "@/api/types";

type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];
type ConceptSchemeCreateRequest = components["schemas"]["ConceptSchemeCreateRequest"];

interface SchemesSearchParams {
  selected?: string;
}

interface SchemesPageContentProps {
  onCreateClick: () => void;
  selectedId?: string;
  onSelectedIdChange: (id?: string) => void;
  taxonomiesById: Map<string, string>;
  taxonomiesError?: Error | null;
  onRetryTaxonomies?: () => void;
}

function SchemesPageContent({
  onCreateClick,
  selectedId,
  onSelectedIdChange,
  taxonomiesById,
  taxonomiesError,
  onRetryTaxonomies,
}: SchemesPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useSchemes();
  const schemes = listResponse?.items || [];

  const filteredData = schemes.filter(
    (scheme: ConceptSchemeResponse) =>
      scheme.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      scheme.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      scheme.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const schemeColumns: ColumnDef<ConceptSchemeResponse>[] = [
    {
      accessorKey: "id",
      header: "ID",
      size: 100,
      cell: (info) => (
        <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
          {(info.getValue() as string).slice(0, 8)}
        </span>
      ),
    },
    {
      accessorKey: "title",
      header: "Name",
      cell: (info) => {
        const schemeId = info.row.original.id;
        return (
          <span
            style={{
              color: "var(--cyan-600, #0891b2)",
              fontWeight: 500,
              cursor: "pointer",
            }}
            onClick={() => onSelectedIdChange(schemeId)}
            data-testid={`scheme-name-${schemeId}`}
          >
            {info.getValue() as string}
          </span>
        );
      },
    },
    {
      accessorKey: "description",
      header: "Description",
      cell: (info) => <span className="muted-text">{(info.getValue() as string) || "—"}</span>,
    },
    {
      accessorKey: "taxonomy_id",
      header: "Parent Taxonomy",
      cell: (info) => {
        const taxonomyId = info.getValue() as string;
        const taxonomyName = taxonomiesById.get(taxonomyId) || "—";
        return (
          <span
            style={{
              backgroundColor: "var(--slate-100, #f1f5f9)",
              color: "var(--slate-700, #334155)",
              padding: "4px 8px",
              borderRadius: "4px",
              fontSize: "var(--text-xs)",
              fontWeight: 500,
            }}
          >
            {taxonomyName}
          </span>
        );
      },
    },
    {
      id: "classCount",
      header: "Classes",
      cell: () => <span className="muted-text">—</span>,
    },
    {
      accessorKey: "last_modified",
      header: "Updated",
      cell: (info) => {
        const date = info.getValue() as string | null;
        return date ? new Date(date).toLocaleDateString() : "—";
      },
    },
    {
      id: "actions",
      header: "",
      size: 40,
      cell: ({ row }) => (
        <button data-testid={`scheme-row-actions-${row.original.id}`} className="btn btn-icon">
          <MoreVertical size={16} style={{ color: "var(--canvas-fg-3)" }} />
        </button>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="stack">
        <Skeleton height={32} width={200} />
        <Skeleton height={40} />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} height={40} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message="Failed to load concept schemes"
        />
      </div>
    );
  }

  if (schemes.length === 0) {
    return (
      <EmptyState
        title={schemesCopy.emptyState.title}
        description={schemesCopy.emptyState.description}
        action={{
          label: schemesCopy.emptyState.actionLabel,
          onClick: onCreateClick,
        }}
      />
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = schemes.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="schemes-page">
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

      {taxonomiesError && onRetryTaxonomies && (
        <div style={{ marginBottom: "var(--space-3)" }}>
          <ErrorBanner
            error={taxonomiesError}
            onRetry={onRetryTaxonomies}
            message="Failed to load parent taxonomies"
            compact
            daemonLogPath="/local-server/logs/context_studio.log"
          />
        </div>
      )}

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={schemesCopy.filteredEmpty.title}
            description={schemesCopy.filteredEmpty.description}
          />
        </div>
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderDrawerContent={(scheme) => (
            <SchemeDrawer
              key={scheme.id}
              scheme={scheme}
              taxonomyName={taxonomiesById.get(scheme.taxonomy_id) || "—"}
              onClose={() => onSelectedIdChange(undefined)}
            />
          )}
        >
          <SchemaTable
            columns={schemeColumns}
            data={filteredData}
            onRowSelect={onSelectedIdChange}
            selectedId={selectedId}
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

export function SchemesIndexPage() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/schema/schemes/" });
  const selectedId = searchParams.selected;
  const createMutation = useCreateScheme();
  const { toast } = useToasts();
  const {
    data: taxonomiesResponse,
    error: taxonomiesError,
    refetch: refetchTaxonomies,
  } = useTaxonomies();
  const taxonomies = taxonomiesResponse?.items || [];

  const taxonomiesById = new Map(taxonomies.map((t) => [t.id, t.title]));

  const handleSelectedIdChange = (id?: string) => {
    navigate({
      to: "/app/schema/schemes",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSubmit = async (data: ConceptSchemeCreateRequest) => {
    setCreateError(null);
    // For now, use the first taxonomy as default. This will be updated in phase with proper selection.
    const taxonomyId = taxonomies[0]?.id;
    if (!taxonomyId) {
      setCreateError("No taxonomies available");
      return;
    }

    try {
      const result = await createMutation.mutateAsync({
        taxonomyId,
        data,
      });
      setShowCreateModal(false);
      toast("success", schemesCopy.create.successToast(result.id));
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create scheme");
    }
  };

  return (
    <>
      <div className="stack">
        <div className="flex-between">
          <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>Concept Schemes</h1>
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="scheme-add-button"
          >
            + New scheme
          </Button>
        </div>
        <div data-testid="schemes-content">
          <SchemesPageContent
            onCreateClick={() => setShowCreateModal(true)}
            selectedId={selectedId}
            onSelectedIdChange={handleSelectedIdChange}
            taxonomiesById={taxonomiesById}
            taxonomiesError={taxonomiesError}
            onRetryTaxonomies={() => refetchTaxonomies()}
          />
        </div>

        <Modal
          open={showCreateModal}
          onClose={() => {
            setShowCreateModal(false);
            setCreateError(null);
          }}
          title="Create Concept Scheme"
          size="sm"
          data-testid="scheme-create-modal"
        >
          {createError && (
            <div style={{ marginBottom: "var(--space-3)" }}>
              <ErrorBanner
                error={new Error(createError)}
                onRetry={() => setCreateError(null)}
                message="Failed to create scheme"
                daemonLogPath="/local-server/logs/context_studio.log"
              />
            </div>
          )}
          <SchemeForm onSubmit={handleCreateSubmit} isLoading={createMutation.isPending} />
        </Modal>
      </div>
    </>
  );
}

export const Route = createFileRoute("/app/schema/schemes/")({
  component: SchemesIndexPage,
  validateSearch: (search: Record<string, unknown>): SchemesSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});

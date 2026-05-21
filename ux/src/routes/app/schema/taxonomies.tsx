import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";
import { useToasts } from "@/components/ui/Toast";
import { Button } from "@tinkermonkey/heimdall-ui";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { TaxonomyForm } from "@/components/schema/TaxonomyForm";
import { TaxonomyDrawer } from "@/components/ontology/TaxonomyDrawer";
import { useTaxonomies, useCreateTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { taxonomiesCopy } from "./taxonomies/-copy";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type TaxonomyCreateRequest = components["schemas"]["TaxonomyCreateRequest"];

interface TaxonomiesSearchParams {
  selected?: string;
}

interface TaxonomiesPageContentProps {
  onCreateClick: () => void;
  selectedId?: string;
  onSelectedIdChange: (id: string | undefined) => void;
}

function TaxonomiesPageContent({
  onCreateClick,
  selectedId,
  onSelectedIdChange,
}: TaxonomiesPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useTaxonomies();
  const taxonomies = listResponse?.items || [];

  const filteredData = taxonomies.filter(
    (tax: TaxonomyResponse) =>
      tax.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      tax.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      tax.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const taxonomyColumns: ColumnDef<TaxonomyResponse>[] = [
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
        const taxonomyId = info.row.original.id;
        return (
          <span
            style={{
              color: "var(--cyan-600, #0891b2)",
              fontWeight: 500,
              cursor: "pointer",
            }}
            onClick={() => onSelectedIdChange(taxonomyId)}
            data-testid={`taxonomy-name-${taxonomyId}`}
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
      accessorKey: "status",
      header: "Status",
      cell: (info) => {
        const status = info.getValue() as string;
        const bgColor =
          status === "draft" ? "var(--amber-100, #fef3c7)" : "var(--green-100, #dcfce7)";
        const textColor =
          status === "draft" ? "var(--amber-800, #78350f)" : "var(--green-800, #166534)";
        return (
          <span
            style={{
              backgroundColor: bgColor,
              color: textColor,
              padding: "4px 8px",
              borderRadius: "4px",
              fontSize: "var(--text-xs)",
              fontWeight: 500,
              textTransform: "capitalize",
            }}
          >
            {status}
          </span>
        );
      },
    },
    {
      id: "stats",
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
        <button data-testid={`taxonomy-row-actions-${row.original.id}`} className="btn btn-icon">
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
        <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load taxonomies" />
      </div>
    );
  }

  if (taxonomies.length === 0) {
    return (
      <EmptyState
        title={taxonomiesCopy.emptyState.title}
        description={taxonomiesCopy.emptyState.description}
        action={{
          label: taxonomiesCopy.emptyState.actionLabel,
          onClick: onCreateClick,
        }}
      />
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = taxonomies.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="taxonomies-page">
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={taxonomiesCopy.filteredEmpty.title}
            description={taxonomiesCopy.filteredEmpty.description}
          />
        </div>
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderDrawerContent={(tax) => (
            <TaxonomyDrawer
              key={tax.id}
              taxonomy={tax}
              onClose={() => onSelectedIdChange(undefined)}
            />
          )}
        >
          <SchemaTable
            columns={taxonomyColumns}
            data={filteredData}
            onRowSelect={onSelectedIdChange}
            selectedId={selectedId}
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

function TaxonomiesPageWrapper() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/schema/taxonomies" });
  const selectedId = searchParams.selected;
  const createMutation = useCreateTaxonomy();
  const { toast } = useToasts();

  const handleSelectedIdChange = (id: string | undefined) => {
    navigate({
      to: "/app/schema/taxonomies",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSubmit = async (data: TaxonomyCreateRequest) => {
    setCreateError(null);
    try {
      const result = await createMutation.mutateAsync(data);
      setShowCreateModal(false);
      handleSelectedIdChange(result.id);
      toast("success", taxonomiesCopy.create.successToast(result.id));
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create taxonomy");
    }
  };

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Schema"
        title="Taxonomies"
        actions={
          <div className="row" style={{ gap: "var(--space-2)" }}>
            <Button variant="ghost" onClick={() => {}} data-testid="taxonomy-import-button">
              Import
            </Button>
            <Button
              variant="primary"
              onClick={() => setShowCreateModal(true)}
              data-testid="taxonomy-add-button"
            >
              + New taxonomy
            </Button>
          </div>
        }
      />
      <div data-testid="taxonomies-content">
        <TaxonomiesPageContent
          onCreateClick={() => setShowCreateModal(true)}
          selectedId={selectedId}
          onSelectedIdChange={handleSelectedIdChange}
        />
      </div>

      <Modal
        open={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Create Taxonomy"
        size="sm"
        data-testid="taxonomy-create-modal"
      >
        {createError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(createError)}
              onRetry={() => setCreateError(null)}
              message="Failed to create taxonomy"
            />
          </div>
        )}
        <TaxonomyForm onSubmit={handleCreateSubmit} isLoading={createMutation.isPending} />
      </Modal>
    </div>
  );
}

export function TaxonomiesPage() {
  return <TaxonomiesPageWrapper />;
}

export const Route = createFileRoute("/app/schema/taxonomies")({
  component: TaxonomiesPage,
  validateSearch: (search: Record<string, unknown>): TaxonomiesSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});

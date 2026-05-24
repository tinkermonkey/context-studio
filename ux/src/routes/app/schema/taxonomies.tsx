import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Button, Modal, PageHeader, RowMenu, Chip, FilterBar, TabBar } from "@tinkermonkey/heimdall-ui";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { TaxonomyForm } from "@/components/schema/TaxonomyForm";
import { TaxonomyDrawer } from "@/components/ontology/TaxonomyDrawer";
import { useTaxonomies, useCreateTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
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

  const taxonomyColumns: Column<TaxonomyResponse>[] = [
    {
      key: "id",
      label: "ID",
      render: (value) => (
        <code className="font-mono text-xs">{(value as string).slice(0, 8)}</code>
      ),
    },
    {
      key: "title",
      label: "Name",
      sortable: true,
      render: (value, row) => (
        <span
          style={{ color: "var(--accent-cyan, #22d3ee)", fontWeight: 500, cursor: "pointer" }}
          onClick={() => onSelectedIdChange(row.id)}
          data-testid={`taxonomy-name-${row.id}`}
        >
          {value as string}
        </span>
      ),
    },
    {
      key: "description",
      label: "Description",
      render: (value) => <span className="opacity-60">{(value as string) || "—"}</span>,
    },
    {
      key: "status",
      label: "Status",
      render: (value) => {
        const status = value as string;
        return <Chip variant={status === "draft" ? "amber" : "emerald"}>{status}</Chip>;
      },
    },
    {
      key: "last_modified",
      label: "Updated",
      render: (value) => {
        const date = value as string | null;
        return date ? new Date(date).toLocaleDateString() : "—";
      },
    },
    {
      key: "created_at",
      label: "",
      width: "40px",
      render: (_, row) => (
        <RowMenu
          data-testid={`taxonomy-row-actions-${row.id}`}
          actions={[
            { id: "edit", label: "Edit", icon: "edit" },
            { id: "clone", label: "Clone", icon: "copy" },
            { type: "separator" },
            { id: "delete", label: "Delete", icon: "trash", danger: true },
          ]}
          onAction={(actionId) => console.log(`Action ${actionId} on taxonomy ${row.id}`)}
        />
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
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={taxonomies.length}
      />

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

  const { data: taxData } = useTaxonomies();
  const { data: schemesData } = useSchemes();
  const { data: classesData } = useClasses();
  const { data: propsData } = useProperties();
  const { data: relsData } = useRelationships();

  const schemaTabs = [
    { id: "taxonomies", label: "Taxonomies", count: taxData?.total },
    { id: "schemes", label: "Schemes", count: schemesData?.total },
    { id: "classes", label: "Classes", count: classesData?.total },
    { id: "properties", label: "Properties", count: propsData?.total },
    { id: "relationships", label: "Relationships", count: relsData?.items?.length ?? relsData?.total },
  ];

  const handleTabNavigate = (tabId: string) => {
    const routes: Record<string, string> = {
      taxonomies: "/app/schema/taxonomies",
      schemes: "/app/schema/schemes",
      classes: "/app/schema/classes",
      properties: "/app/schema/properties",
      relationships: "/app/schema/relationships",
    };
    navigate({ to: routes[tabId] as any });
  };

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
        idChip="/schema/taxonomies"
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

      <TabBar tabs={schemaTabs} activeTabId="taxonomies" onSelectTab={handleTabNavigate} />

      <div data-testid="taxonomies-content">
        <TaxonomiesPageContent
          onCreateClick={() => setShowCreateModal(true)}
          selectedId={selectedId}
          onSelectedIdChange={handleSelectedIdChange}
        />
      </div>

      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Create Taxonomy"
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

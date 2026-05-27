import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import {
  Button,
  Modal,
  PageHeader,
  RowMenu,
  Chip,
  FilterBar,
  TabBar,
  Icon,
  VersionPill,
} from "@tinkermonkey/heimdall-ui";
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
      label: "Identifier",
      width: "160px",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>
          {(value as string).slice(0, 8)}
        </span>
      ),
    },
    {
      key: "title",
      label: "Title",
      sortable: true,
      render: (value) => <span style={{ fontWeight: 500 }}>{value as string}</span>,
    },
    {
      key: "description",
      label: "Description",
      render: (value) => (
        <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>
          {(value as string) || "—"}
        </span>
      ),
    },
    {
      key: "status",
      label: "Status",
      width: "120px",
      render: (value) => {
        const status = value as string;
        return <Chip variant={status === "draft" ? "amber" : "emerald"}>{status}</Chip>;
      },
    },
    {
      key: "last_modified",
      label: "Updated",
      width: "120px",
      render: (value) => {
        const date = value as string | null;
        return (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11.5,
              color: "rgb(var(--canvas-fg-3))",
            }}
          >
            {date ? new Date(date).toLocaleDateString() : "—"}
          </span>
        );
      },
    },
    {
      key: "version",
      label: "Ver",
      width: "60px",
      render: (value) => <VersionPill>{value as number}</VersionPill>,
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
        <div className="skeleton" style={{ height: 32, width: 200 }} />
        <div className="skeleton" style={{ height: 40 }} />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 40 }} />
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
    <div data-testid="taxonomies-page" className="stack">
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={taxonomies.length}
      />

      {showFilteredEmpty ? (
        <EmptyState
          title={taxonomiesCopy.filteredEmpty.title}
          description={taxonomiesCopy.filteredEmpty.description}
        />
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderInspectorContent={(tax) => (
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
    {
      id: "relationships",
      label: "Relationships",
      count: relsData?.items?.length ?? relsData?.total,
    },
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
        eyebrow="SCHEMA · node_type · taxonomy"
        title="Taxonomies"
        idChip="/schema/taxonomies"
        subtitle="A taxonomy is the top-level domain. It groups concept schemes — each scheme is a focused area of knowledge."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}} data-testid="taxonomy-export-button">
              <Icon name="download" size={13} /> Export
            </Button>
            <Button
              variant="primary"
              onClick={() => setShowCreateModal(true)}
              data-testid="taxonomy-add-button"
            >
              <Icon name="plus" size={13} /> New taxonomy
            </Button>
          </>
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

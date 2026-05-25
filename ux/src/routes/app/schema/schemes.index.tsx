import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Button, Modal, PageHeader, RowMenu, Chip, FilterBar, TabBar } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { SchemeForm } from "@/components/schema/SchemeForm";
import { SchemeDrawer } from "@/components/ontology/SchemeDrawer";
import { useSchemes, useCreateScheme } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
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

  const schemeColumns: Column<ConceptSchemeResponse>[] = [
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
          data-testid={`scheme-name-${row.id}`}
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
      key: "taxonomy_id",
      label: "Parent Taxonomy",
      render: (value) => {
        const taxName = taxonomiesById.get(value as string) || "—";
        return <Chip variant="neutral">{taxName}</Chip>;
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
          data-testid={`scheme-row-actions-${row.id}`}
          actions={[
            { id: "edit", label: "Edit", icon: "edit" },
            { id: "clone", label: "Clone", icon: "copy" },
            { type: "separator" },
            { id: "delete", label: "Delete", icon: "trash", danger: true },
          ]}
          onAction={(actionId) => console.log(`Action ${actionId} on scheme ${row.id}`)}
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
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={schemes.length}
      />

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

  const { data: schemesData } = useSchemes();
  const { data: classesData } = useClasses();
  const { data: propsData } = useProperties();
  const { data: relsData } = useRelationships();

  const schemaTabs = [
    { id: "taxonomies", label: "Taxonomies", count: taxonomiesResponse?.total },
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

  const handleSelectedIdChange = (id?: string) => {
    navigate({
      to: "/app/schema/schemes",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSubmit = async (data: ConceptSchemeCreateRequest) => {
    setCreateError(null);
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
        <PageHeader
          eyebrow="Schema"
          title="Concept Schemes"
          idChip="/schema/schemes"
          actions={
            <Button
              variant="primary"
              onClick={() => setShowCreateModal(true)}
              data-testid="scheme-add-button"
            >
              + New scheme
            </Button>
          }
        />

        <TabBar tabs={schemaTabs} activeTabId="schemes" onSelectTab={handleTabNavigate} />

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
          isOpen={showCreateModal}
          onClose={() => {
            setShowCreateModal(false);
            setCreateError(null);
          }}
          title="Create Concept Scheme"
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

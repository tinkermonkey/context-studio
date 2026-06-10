import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import {
  Button,
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
import { CreateDrawer } from "@/components/crud/CreateDrawer";
import { SchemeDrawer } from "@/components/ontology/SchemeDrawer";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { schemesCopy } from "./schemes/-copy";
import type { components } from "@/api/types";

type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];

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
      key: "taxonomy_id",
      label: "Taxonomy",
      width: "160px",
      render: (value) => {
        const taxName = taxonomiesById.get(value as string) || "—";
        return <Chip variant="neutral">{taxName}</Chip>;
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
    <div data-testid="schemes-page" className="stack">
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={schemes.length}
      />

      {taxonomiesError && onRetryTaxonomies && (
        <ErrorBanner
          error={taxonomiesError}
          onRetry={onRetryTaxonomies}
          message="Failed to load parent taxonomies"
          compact
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      )}

      {showFilteredEmpty ? (
        <EmptyState
          title={schemesCopy.filteredEmpty.title}
          description={schemesCopy.filteredEmpty.description}
        />
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderInspectorContent={(scheme) => (
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
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/schema/schemes/" });
  const selectedId = searchParams.selected;
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

  const handleSelectedIdChange = (id?: string) => {
    navigate({
      to: "/app/schema/schemes",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSuccess = (entity: { id: string; title?: string }) => {
    toast("success", schemesCopy.create.successToast(entity.id));
  };

  return (
    <div className="stack">
      <PageHeader
        eyebrow="SCHEMA · node_type · concept_scheme"
        title="Concept Schemes"
        idChip="/schema/schemes"
        subtitle="A concept scheme is a focused vocabulary inside a taxonomy. Classes belong to exactly one scheme."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}}>
              <Icon name="download" size={13} /> Export
            </Button>
            <Button
              variant="primary"
              onClick={() => setShowCreateDrawer(true)}
              data-testid="scheme-add-button"
            >
              <Icon name="plus" size={13} /> New scheme
            </Button>
          </>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="schemes" onSelectTab={handleTabNavigate} />

      <div data-testid="schemes-content">
        <SchemesPageContent
          onCreateClick={() => setShowCreateDrawer(true)}
          selectedId={selectedId}
          onSelectedIdChange={handleSelectedIdChange}
          taxonomiesById={taxonomiesById}
          taxonomiesError={taxonomiesError}
          onRetryTaxonomies={() => refetchTaxonomies()}
        />
      </div>

      <CreateDrawer
        entityType="scheme"
        isOpen={showCreateDrawer}
        onClose={() => setShowCreateDrawer(false)}
        onSuccess={handleCreateSuccess}
        data-testid="scheme-create-drawer"
      />
    </div>
  );
}

export const Route = createFileRoute("/app/schema/schemes/")({
  component: SchemesIndexPage,
  validateSearch: (search: Record<string, unknown>): SchemesSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});

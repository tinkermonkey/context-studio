import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
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
import { PropertyDrawer } from "@/components/ontology/PropertyDrawer";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { propertiesCopy } from "./properties/-copy";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

interface PropertiesPageContentProps {
  onCreateClick: () => void;
}

function relevanceChip(isRelevant: boolean | null | undefined) {
  if (isRelevant === true) return <Chip variant="emerald">relevant</Chip>;
  if (isRelevant === false) return <Chip variant="rose">irrelevant</Chip>;
  return <Chip variant="neutral">unevaluated</Chip>;
}

function PropertiesPageContent({ onCreateClick }: PropertiesPageContentProps) {
  const [selectedId, setSelectedId] = useState<string>();
  const [searchFilter, setSearchFilter] = useState("");
  const { data: listResponse, isLoading, error, refetch } = useProperties();
  const properties = listResponse?.items || [];

  const filteredData = properties.filter(
    (prop: PropertyDefinitionResponse) =>
      prop.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      prop.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      prop.identifier.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const propertyColumns: Column<PropertyDefinitionResponse>[] = [
    {
      key: "identifier",
      label: "Identifier",
      width: "180px",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, fontWeight: 500 }}>
          {value as string}
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
      key: "is_relevant",
      label: "Relevance",
      width: "140px",
      render: (value) => relevanceChip(value as boolean | null | undefined),
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
          data-testid={`property-row-actions-${row.id}`}
          actions={[
            { id: "edit", label: "Edit", icon: "edit" },
            { id: "clone", label: "Clone", icon: "copy" },
            { type: "separator" },
            { id: "delete", label: "Delete", icon: "trash", danger: true },
          ]}
          onAction={(actionId) => console.log(`Action ${actionId} on property ${row.id}`)}
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
        <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load properties" />
      </div>
    );
  }

  if (properties.length === 0) {
    return (
      <EmptyState
        title={propertiesCopy.emptyState.title}
        description={propertiesCopy.emptyState.description}
        action={{
          label: propertiesCopy.emptyState.actionLabel,
          onClick: onCreateClick,
        }}
      />
    );
  }

  return (
    <div data-testid="properties-page" className="stack">
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by identifier, title, or description…"
        showingCount={filteredData.length}
        totalCount={properties.length}
      />
      <SchemaPageLayout
        data={filteredData}
        selectedId={selectedId}
        renderInspectorContent={(prop) => (
          <PropertyDrawer key={prop.id} property={prop} onClose={() => setSelectedId(undefined)} />
        )}
      >
        <SchemaTable
          columns={propertyColumns}
          data={filteredData}
          onRowSelect={setSelectedId}
          selectedId={selectedId}
        />
      </SchemaPageLayout>
    </div>
  );
}

function PropertiesPageWrapper() {
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);
  const navigate = useNavigate();
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

  const handleCreateSuccess = (_entity: { id: string; title?: string }) => {
    toast("success", propertiesCopy.create.successToast);
  };

  return (
    <div className="stack">
      <PageHeader
        eyebrow="SCHEMA · node_type · property_definition"
        title="Properties"
        idChip="/schema/properties"
        subtitle="Property definitions are the named predicates used by relationships. A tri-state relevance flag drives which appear in the inferred graph."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}}>
              <Icon name="filter" size={13} /> Filter
            </Button>
            <Button
              variant="primary"
              onClick={() => setShowCreateDrawer(true)}
              data-testid="property-add-button"
            >
              <Icon name="plus" size={13} /> New property
            </Button>
          </>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="properties" onSelectTab={handleTabNavigate} />

      <div data-testid="properties-content">
        <PropertiesPageContent onCreateClick={() => setShowCreateDrawer(true)} />
      </div>

      <CreateDrawer
        entityType="property"
        isOpen={showCreateDrawer}
        onClose={() => setShowCreateDrawer(false)}
        onSuccess={handleCreateSuccess}
        data-testid="property-create-drawer"
      />
    </div>
  );
}

export function PropertiesPage() {
  return <PropertiesPageWrapper />;
}

export const Route = createFileRoute("/app/schema/properties")({
  component: PropertiesPage,
});

import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Button, Modal, PageHeader, RowMenu, FilterBar, TabBar } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { PropertyDefinitionForm } from "@/components/schema/PropertyDefinitionForm";
import { PropertyDrawer } from "@/components/ontology/PropertyDrawer";
import { useProperties, useCreateProperty } from "@/api/hooks/ontology/useProperties";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { ApiError } from "@/api/client/interceptors";
import { propertiesCopy } from "./properties/-copy";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];
type PropertyDefinitionCreateRequest = components["schemas"]["PropertyDefinitionCreateRequest"];
type PropertyDefinitionUpdateRequest = components["schemas"]["PropertyDefinitionUpdateRequest"];

interface PropertiesPageContentProps {
  onCreateClick: () => void;
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
      render: (value) => (
        <span style={{ color: "var(--accent-cyan, #22d3ee)", fontWeight: 500 }}>
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
    <div data-testid="properties-page">
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={properties.length}
      />
      <SchemaPageLayout
        data={filteredData}
        selectedId={selectedId}
        renderDrawerContent={(prop) => (
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
  const [showCreateModal, setShowCreateModal] = useState(false);
  const createMutation = useCreateProperty();
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

  const handleCreateSubmit = async (
    data: PropertyDefinitionCreateRequest | PropertyDefinitionUpdateRequest,
  ) => {
    try {
      if ("identifier" in data) {
        await createMutation.mutateAsync(data as PropertyDefinitionCreateRequest);
      }
      setShowCreateModal(false);
      toast("success", propertiesCopy.create.successToast);
    } catch (error) {
      const message = error instanceof ApiError ? error.detail : "Failed to create property";
      toast("error", message);
    }
  };

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Schema"
        title="Property Definitions"
        idChip="/schema/property-definitions"
        actions={
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="property-add-button"
          >
            + Add property
          </Button>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="properties" onSelectTab={handleTabNavigate} />

      <div data-testid="properties-content">
        <PropertiesPageContent onCreateClick={() => setShowCreateModal(true)} />
      </div>

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create Property"
        data-testid="property-create-modal"
      >
        <PropertyDefinitionForm
          onSubmit={handleCreateSubmit}
          isLoading={createMutation.isPending}
        />
      </Modal>
    </div>
  );
}

export function PropertiesPage() {
  return <PropertiesPageWrapper />;
}

export const Route = createFileRoute("/app/schema/properties")({
  component: PropertiesPage,
});

import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Button, Modal, PageHeader, FilterBar, TabBar, Icon } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { RelationshipDrawer } from "@/components/ontology/RelationshipDrawer";
import { RelationshipForm } from "@/components/schema/RelationshipForm";
import { useRelationships, useCreateRelationship } from "@/api/hooks/ontology/useRelationships";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useToasts } from "@/components/ui/Toast";
import { relationshipsCopy } from "./relationships/-copy";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];

interface RelationshipsPageContentProps {
  classesById: Map<string, string>;
  propertiesById: Map<string, { title: string; identifier: string }>;
  classesError?: Error | null;
  onRetryClasses?: () => void;
  propertiesError?: Error | null;
  onRetryProperties?: () => void;
  onCreateClick?: () => void;
}

function RelationshipsPageContent({
  classesById,
  propertiesById,
  classesError,
  onRetryClasses,
  propertiesError,
  onRetryProperties,
  onCreateClick,
}: RelationshipsPageContentProps) {
  const [selectedId, setSelectedId] = useState<string>();
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useRelationships();
  const relationships = listResponse?.items || [];

  const filteredData = relationships.filter((rel: RelationshipResponse) => {
    const sourceClassName = classesById.get(rel.source_id)?.toLowerCase() ?? "";
    const targetClassName = classesById.get(rel.target_id)?.toLowerCase() ?? "";
    const prop = propertiesById.get(rel.property_definition_id);
    const propertyName = (prop?.title ?? "").toLowerCase();
    const search = searchFilter.toLowerCase();
    return (
      sourceClassName.includes(search) ||
      targetClassName.includes(search) ||
      propertyName.includes(search)
    );
  });

  const relationshipColumns: Column<RelationshipResponse>[] = [
    {
      key: "id",
      label: "Identifier",
      width: "120px",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>
          {(value as string).slice(0, 8)}
        </span>
      ),
    },
    {
      key: "source_id",
      label: "Source",
      render: (value) => (
        <span style={{ fontWeight: 500 }}>{classesById.get(value as string) || "—"}</span>
      ),
    },
    {
      key: "property_definition_id",
      label: "Predicate",
      width: "200px",
      render: (value) => {
        const prop = propertiesById.get(value as string);
        return (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11.5,
              color: "rgb(var(--canvas-fg-3))",
            }}
          >
            — {prop?.identifier ?? "?"} →
          </span>
        );
      },
    },
    {
      key: "target_id",
      label: "Target",
      render: (value) => (
        <span style={{ fontWeight: 500 }}>{classesById.get(value as string) || "—"}</span>
      ),
    },
    {
      key: "created_at",
      label: "Created",
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
          message="Failed to load relationships"
        />
      </div>
    );
  }

  if (relationships.length === 0) {
    return (
      <EmptyState
        title={relationshipsCopy.emptyState.title}
        description={relationshipsCopy.emptyState.description}
        action={{
          label: relationshipsCopy.emptyState.actionLabel,
          onClick: () => onCreateClick?.(),
        }}
      />
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = relationships.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="relationships-page" className="stack">
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by source, predicate, or target…"
        showingCount={filteredData.length}
        totalCount={relationships.length}
      />

      {classesError && onRetryClasses && (
        <ErrorBanner
          error={classesError}
          onRetry={onRetryClasses}
          message="Failed to load classes"
          compact
        />
      )}

      {propertiesError && onRetryProperties && (
        <ErrorBanner
          error={propertiesError}
          onRetry={onRetryProperties}
          message="Failed to load properties"
          compact
        />
      )}

      {showFilteredEmpty ? (
        <EmptyState
          title={relationshipsCopy.filteredEmpty.title}
          description={relationshipsCopy.filteredEmpty.description}
        />
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderInspectorContent={(rel) => (
            <RelationshipDrawer
              key={rel.id}
              relationship={rel}
              sourceName={classesById.get(rel.source_id) || "—"}
              targetName={classesById.get(rel.target_id) || "—"}
              propertyName={propertiesById.get(rel.property_definition_id)?.title || "—"}
              onClose={() => setSelectedId(undefined)}
            />
          )}
        >
          <SchemaTable
            columns={relationshipColumns}
            data={filteredData}
            onRowSelect={setSelectedId}
            selectedId={selectedId}
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

function RelationshipsPageWrapper() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { data: classesResponse, error: classesError, refetch: refetchClasses } = useClasses();
  const {
    data: propertiesResponse,
    error: propertiesError,
    refetch: refetchProperties,
  } = useProperties();
  const createMutation = useCreateRelationship();
  const { toast } = useToasts();

  const classes = classesResponse?.items || [];
  const properties = propertiesResponse?.items || [];

  const classesById = new Map(classes.map((c) => [c.id, c.title]));
  const propertiesById = new Map(
    properties.map((p) => [p.id, { title: p.title, identifier: p.identifier }]),
  );

  const { data: taxData } = useTaxonomies();
  const { data: schemesData } = useSchemes();
  const { data: propsData } = useProperties();
  const { data: relsData } = useRelationships();

  const schemaTabs = [
    { id: "taxonomies", label: "Taxonomies", count: taxData?.total },
    { id: "schemes", label: "Schemes", count: schemesData?.total },
    { id: "classes", label: "Classes", count: classesResponse?.total },
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

  const handleCreateSubmit = async (data: components["schemas"]["RelationshipCreateRequest"]) => {
    setCreateError(null);
    try {
      await createMutation.mutateAsync(data);
      setShowCreateModal(false);
      toast("success", "Relationship created successfully");
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create relationship");
    }
  };

  return (
    <div className="stack">
      <PageHeader
        eyebrow="SCHEMA · node_type · relationship"
        title="Relationships"
        idChip="/schema/relationships"
        subtitle="A relationship is a typed triple (s, p, o) between two graph nodes. Source and confidence are tracked separately from the data."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}}>
              <Icon name="download" size={13} /> Export
            </Button>
            <Button
              variant="primary"
              onClick={() => setShowCreateModal(true)}
              data-testid="relationship-add-button"
            >
              <Icon name="plus" size={13} /> New relationship
            </Button>
          </>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="relationships" onSelectTab={handleTabNavigate} />

      <div data-testid="relationships-content">
        <RelationshipsPageContent
          classesById={classesById}
          propertiesById={propertiesById}
          classesError={classesError}
          onRetryClasses={() => refetchClasses()}
          propertiesError={propertiesError}
          onRetryProperties={() => refetchProperties()}
          onCreateClick={() => setShowCreateModal(true)}
        />
      </div>

      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Create Relationship"
        data-testid="relationship-create-modal"
      >
        {createError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(createError)}
              onRetry={() => setCreateError(null)}
              message="Failed to create relationship"
            />
          </div>
        )}
        <RelationshipForm
          onSubmit={handleCreateSubmit}
          isLoading={createMutation.isPending}
          classes={classes}
          properties={properties}
        />
      </Modal>
    </div>
  );
}

export function RelationshipsPage() {
  return <RelationshipsPageWrapper />;
}

export const Route = createFileRoute("/app/schema/relationships")({
  component: RelationshipsPage,
});

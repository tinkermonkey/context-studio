import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical, ChevronDown } from "lucide-react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar, type FilterChip } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { RelationshipDrawer } from "@/components/ontology/RelationshipDrawer";
import { RelationshipForm } from "@/components/schema/RelationshipForm";
import { useRelationships, useCreateRelationship } from "@/api/hooks/ontology/useRelationships";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useToasts } from "@/components/ui/Toast";
import { relationshipsCopy } from "./relationships/-copy";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];

interface RelationshipsPageContentProps {
  classesById: Map<string, string>;
  propertiesById: Map<string, string>;
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
  const [sourceClassFilter, setSourceClassFilter] = useState<string>();
  const [targetClassFilter, setTargetClassFilter] = useState<string>();

  const { data: listResponse, isLoading, error, refetch } = useRelationships();
  const relationships = listResponse?.items || [];

  const filteredData = relationships.filter((rel: RelationshipResponse) => {
    const sourceClassName = classesById.get(rel.source_id)?.toLowerCase() ?? "";
    const targetClassName = classesById.get(rel.target_id)?.toLowerCase() ?? "";
    const propertyName = propertiesById.get(rel.property_definition_id)?.toLowerCase() ?? "";
    const search = searchFilter.toLowerCase();

    const matchesSearch =
      sourceClassName.includes(search) ||
      targetClassName.includes(search) ||
      propertyName.includes(search);

    const matchesSourceFilter = !sourceClassFilter || rel.source_id === sourceClassFilter;
    const matchesTargetFilter = !targetClassFilter || rel.target_id === targetClassFilter;

    return matchesSearch && matchesSourceFilter && matchesTargetFilter;
  });

  const filterChips: FilterChip[] = [
    ...(sourceClassFilter
      ? [
          {
            label: `Source: ${classesById.get(sourceClassFilter) || sourceClassFilter}`,
            value: sourceClassFilter,
            onRemove: () => setSourceClassFilter(undefined),
          },
        ]
      : []),
    ...(targetClassFilter
      ? [
          {
            label: `Target: ${classesById.get(targetClassFilter) || targetClassFilter}`,
            value: targetClassFilter,
            onRemove: () => setTargetClassFilter(undefined),
          },
        ]
      : []),
  ];

  const relationshipColumns: ColumnDef<RelationshipResponse>[] = [
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
      accessorKey: "property_definition_id",
      header: "Name",
      cell: (info) => (
        <span
          style={{
            color: "var(--cyan-600, #0891b2)",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          {propertiesById.get(info.getValue() as string) || "—"}
        </span>
      ),
    },
    {
      accessorKey: "source_id",
      header: "Source Class",
      cell: (info) => (
        <span className="muted-text">{classesById.get(info.getValue() as string) || "—"}</span>
      ),
    },
    {
      accessorKey: "target_id",
      header: "Target Class",
      cell: (info) => (
        <span className="muted-text">{classesById.get(info.getValue() as string) || "—"}</span>
      ),
    },
    {
      id: "actions",
      header: "",
      size: 40,
      cell: ({ row }) => (
        <button
          data-testid={`relationship-row-actions-${row.original.id}`}
          className="btn btn-icon"
        >
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
          onClick: () => {
            onCreateClick?.();
          },
        }}
      />
    );
  }

  const hasFilters = !!searchFilter || !!sourceClassFilter || !!targetClassFilter;
  const showFilteredEmpty = relationships.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="relationships-page">
      <div className="stack">
        <div className="row" style={{ flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <select
              value={sourceClassFilter || ""}
              onChange={(e) => setSourceClassFilter(e.target.value || undefined)}
              data-testid="relationship-source-class-filter"
              style={{
                padding: "6px 8px",
                borderRadius: "4px",
                border: "1px solid rgb(var(--canvas-fg-4))",
                backgroundColor: "var(--canvas-bg, #ffffff)",
                cursor: "pointer",
                fontSize: "var(--text-sm)",
                appearance: "none",
                paddingRight: "24px",
              }}
            >
              <option value="">Source Class</option>
              {Array.from(classesById.entries()).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={14}
              style={{
                position: "absolute",
                right: "8px",
                top: "50%",
                transform: "translateY(-50%)",
                pointerEvents: "none",
                color: "var(--canvas-fg-3)",
              }}
            />
          </div>

          <div style={{ position: "relative" }}>
            <select
              value={targetClassFilter || ""}
              onChange={(e) => setTargetClassFilter(e.target.value || undefined)}
              data-testid="relationship-target-class-filter"
              style={{
                padding: "6px 8px",
                borderRadius: "4px",
                border: "1px solid rgb(var(--canvas-fg-4))",
                backgroundColor: "var(--canvas-bg, #ffffff)",
                cursor: "pointer",
                fontSize: "var(--text-sm)",
                appearance: "none",
                paddingRight: "24px",
              }}
            >
              <option value="">Target Class</option>
              {Array.from(classesById.entries()).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={14}
              style={{
                position: "absolute",
                right: "8px",
                top: "50%",
                transform: "translateY(-50%)",
                pointerEvents: "none",
                color: "var(--canvas-fg-3)",
              }}
            />
          </div>
        </div>

        <FilterBar
          searchValue={searchFilter}
          onSearchChange={setSearchFilter}
          filterChips={filterChips}
        />
      </div>

      {classesError && onRetryClasses && (
        <div style={{ marginBottom: "var(--space-3)" }}>
          <ErrorBanner
            error={classesError}
            onRetry={onRetryClasses}
            message="Failed to load classes"
            compact
          />
        </div>
      )}

      {propertiesError && onRetryProperties && (
        <div style={{ marginBottom: "var(--space-3)" }}>
          <ErrorBanner
            error={propertiesError}
            onRetry={onRetryProperties}
            message="Failed to load properties"
            compact
          />
        </div>
      )}

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={relationshipsCopy.filteredEmpty.title}
            description={relationshipsCopy.filteredEmpty.description}
          />
        </div>
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderDrawerContent={(rel) => (
            <RelationshipDrawer
              key={rel.id}
              relationship={rel}
              sourceName={classesById.get(rel.source_id) || "—"}
              targetName={classesById.get(rel.target_id) || "—"}
              propertyName={propertiesById.get(rel.property_definition_id) || "—"}
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
  const propertiesById = new Map(properties.map((p) => [p.id, p.title]));

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
        eyebrow="Schema"
        title="Relationships"
        actions={
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="relationship-add-button"
          >
            + Add relationship
          </Button>
        }
      />
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
        open={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Create Relationship"
        size="sm"
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

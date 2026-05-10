import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";
import { useToasts } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { PropertyDefinitionForm } from "@/components/schema/PropertyDefinitionForm";
import { PropertyDrawer } from "@/components/ontology/PropertyDrawer";
import { useProperties, useCreateProperty } from "@/api/hooks/ontology/useProperties";
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

  const propertyColumns: ColumnDef<PropertyDefinitionResponse>[] = [
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
      cell: (info) => (
        <span
          style={{
            color: "var(--cyan-600, #0891b2)",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          {info.getValue() as string}
        </span>
      ),
    },
    {
      accessorKey: "description",
      header: "Description",
      cell: (info) => (
        <span style={{ color: "var(--canvas-fg-2)" }}>{(info.getValue() as string) || "—"}</span>
      ),
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
        <button
          data-testid={`property-row-actions-${row.original.id}`}
          style={{
            background: "none",
            border: "none",
            padding: 0,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
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
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />
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
  const { toast } = useToasts();

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
      <div className="flex-between">
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>Property Definitions</h1>
        <Button
          variant="primary"
          onClick={() => setShowCreateModal(true)}
          data-testid="property-add-button"
        >
          + Add property
        </Button>
      </div>
      <div data-testid="properties-content">
        <PropertiesPageContent onCreateClick={() => setShowCreateModal(true)} />
      </div>

      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create Property"
        size="sm"
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

import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
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
import { ClassEditor } from "@/components/ontology/ClassEditor";
import { ClassDrawer } from "@/components/ontology/ClassDrawer";
import { useClasses, useCreateClass } from "@/api/hooks/ontology/useClasses";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { classesCopy } from "./classes/-copy";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

interface ClassesSearchParams {
  selected?: string;
}

interface ClassesPageContentProps {
  onCreateClick: () => void;
  selectedId?: string;
  onSelectedIdChange: (id?: string) => void;
}

function ClassesPageContent({
  onCreateClick,
  selectedId,
  onSelectedIdChange,
}: ClassesPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useClasses();
  const classes = listResponse?.items || [];

  const { data: schemesResponse, error: schemesError, refetch: refetchSchemes } = useSchemes();
  const schemes = schemesResponse?.items || [];

  const schemeMap = new Map(schemes.map((s) => [s.id, s.title]));
  const classMap = new Map(classes.map((c) => [c.id, c.title]));

  const filteredData = classes.filter(
    (cls: ClassResponse) =>
      cls.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      cls.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      cls.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const classColumns: ColumnDef<ClassResponse>[] = [
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
        const classId = info.row.original.id;
        return (
          <span
            style={{
              color: "var(--cyan-600, #0891b2)",
              fontWeight: 500,
              cursor: "pointer",
            }}
            data-testid={`class-name-${classId}`}
            onClick={() => onSelectedIdChange(classId)}
          >
            {info.getValue() as string}
          </span>
        );
      },
    },
    {
      accessorKey: "concept_scheme_id",
      header: "Domain",
      cell: (info) => {
        const schemeId = info.getValue() as string;
        const schemeName = schemeMap.get(schemeId) || "Unknown";
        return (
          <span
            style={{
              backgroundColor: "var(--canvas-bg-2)",
              color: "var(--canvas-fg)",
              padding: "4px 8px",
              borderRadius: "4px",
              fontSize: "var(--text-xs)",
              fontWeight: 500,
            }}
            data-testid={`class-domain-${info.row.original.id}`}
          >
            {schemeName}
          </span>
        );
      },
    },
    {
      accessorKey: "parent_class_id",
      header: "Parent Class",
      cell: (info) => {
        const parentId = info.getValue() as string | null | undefined;
        if (!parentId) return <span style={{ color: "var(--canvas-fg-3)" }}>—</span>;
        const parentName = classMap.get(parentId) || "Unknown";
        return (
          <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
            {parentId.slice(0, 8)} ({parentName})
          </span>
        );
      },
    },
    {
      id: "propertyCount",
      header: "Properties",
      cell: ({ row }) => (
        <span className="muted-text">
          {row.original.data_properties?.length ?? 0}
        </span>
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
          data-testid={`class-row-actions-${row.original.id}`}
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
          message="Failed to load classes"
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  if (classes.length === 0) {
    return (
      <EmptyState
        title={classesCopy.emptyState.title}
        description={classesCopy.emptyState.description}
        action={{
          label: classesCopy.emptyState.actionLabel,
          onClick: onCreateClick,
        }}
      />
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = classes.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="classes-page">
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

      {schemesError && (
        <div style={{ marginBottom: "var(--space-3)" }}>
          <ErrorBanner
            error={schemesError as Error}
            onRetry={() => refetchSchemes()}
            message="Failed to load domains"
            compact
            daemonLogPath="/local-server/logs/context_studio.log"
          />
        </div>
      )}

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={classesCopy.filteredEmpty.title}
            description={classesCopy.filteredEmpty.description}
          />
        </div>
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderDrawerContent={(cls) => (
            <ClassDrawer
              key={cls.id}
              classData={cls}
              onClose={() => onSelectedIdChange(undefined)}
            />
          )}
        >
          <SchemaTable
            columns={classColumns}
            data={filteredData}
            onRowSelect={onSelectedIdChange}
            selectedId={selectedId}
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

function ClassesPageWrapper() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/schema/classes" });
  const selectedId = searchParams.selected;
  const createMutation = useCreateClass();
  const { toast } = useToasts();

  const handleSelectedIdChange = (id?: string) => {
    navigate({
      to: "/app/schema/classes",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSubmit = async (
    data: { title: string; description?: string | null; parent_class_id?: string | null },
    schemeId?: string,
  ) => {
    setCreateError(null);
    try {
      if (!schemeId) {
        setCreateError("Please select a domain");
        return;
      }
      await createMutation.mutateAsync({
        schemeId,
        data: {
          title: data.title,
          description: data.description,
          parent_class_id: data.parent_class_id,
        },
      });
      setShowCreateModal(false);
      toast("success", classesCopy.create.successToast);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create class");
    }
  };

  return (
    <div className="stack">
      <div className="flex-between">
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>Classes</h1>
        <div className="row">
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="class-add-button"
          >
            + New class
          </Button>
        </div>
      </div>
      <div data-testid="classes-content">
        <ClassesPageContent
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
        title="Create Class"
        size="md"
        data-testid="class-create-modal"
      >
        {createError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(createError)}
              onRetry={() => setCreateError(null)}
              message="Failed to create class"
              daemonLogPath="/local-server/logs/context_studio.log"
            />
          </div>
        )}
        <ClassEditor onSubmit={handleCreateSubmit} isLoading={createMutation.isPending} />
      </Modal>
    </div>
  );
}

export function ClassesPage() {
  return <ClassesPageWrapper />;
}

export const Route = createFileRoute("/app/schema/classes")({
  component: ClassesPage,
  validateSearch: (search: Record<string, unknown>): ClassesSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});

import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Button, Modal, PageHeader, RowMenu, Chip, FilterBar, TabBar, SegmentedControl } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { ClassEditor } from "@/components/ontology/ClassEditor";
import { ClassDrawer } from "@/components/ontology/ClassDrawer";
import { useClasses, useCreateClass } from "@/api/hooks/ontology/useClasses";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
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
  const [domainFilter, setDomainFilter] = useState<string>("all");

  const { data: listResponse, isLoading, error, refetch } = useClasses();
  const classes = listResponse?.items || [];

  const { data: schemesResponse, error: schemesError, refetch: refetchSchemes } = useSchemes();
  const schemes = schemesResponse?.items || [];

  const schemeMap = new Map(schemes.map((s) => [s.id, s.title]));
  const classMap = new Map(classes.map((c) => [c.id, c.title]));

  const domainOptions = [
    { value: "all", label: "All" },
    ...schemes.map((s) => ({ value: s.id, label: s.title })),
  ];

  const filteredData = classes
    .filter((cls: ClassResponse) => domainFilter === "all" || cls.concept_scheme_id === domainFilter)
    .filter(
      (cls: ClassResponse) =>
        cls.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
        cls.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
        cls.id.toLowerCase().includes(searchFilter.toLowerCase()),
    );

  const classColumns: Column<ClassResponse>[] = [
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
          data-testid={`class-name-${row.id}`}
          onClick={() => onSelectedIdChange(row.id)}
        >
          {value as string}
        </span>
      ),
    },
    {
      key: "concept_scheme_id",
      label: "Domain",
      render: (value, row) => {
        const schemeName = schemeMap.get(value as string) || "Unknown";
        return (
          <Chip variant="neutral" data-testid={`class-domain-${row.id}`}>
            {schemeName}
          </Chip>
        );
      },
    },
    {
      key: "parent_class_id",
      label: "Parent Class",
      render: (value) => {
        const parentId = value as string | null | undefined;
        if (!parentId) return <span className="opacity-60">—</span>;
        const parentName = classMap.get(parentId) || "Unknown";
        return (
          <code className="font-mono text-xs">
            {parentId.slice(0, 8)} ({parentName})
          </code>
        );
      },
    },
    {
      key: "version",
      label: "Properties",
      render: (_, row) => (
        <span className="opacity-60">{row.data_properties?.length ?? 0}</span>
      ),
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
          data-testid={`class-row-actions-${row.id}`}
          actions={[
            { id: "edit", label: "Edit", icon: "edit" },
            { id: "clone", label: "Clone", icon: "copy" },
            { type: "separator" },
            { id: "delete", label: "Delete", icon: "trash", danger: true },
          ]}
          onAction={(actionId) => console.log(`Action ${actionId} on class ${row.id}`)}
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

  const hasFilters = !!searchFilter || domainFilter !== "all";
  const showFilteredEmpty = classes.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="classes-page">
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={classes.length}
      />

      {schemes.length > 0 && (
        <SegmentedControl
          value={domainFilter}
          onChange={(v) => setDomainFilter(v as string)}
          options={domainOptions}
        />
      )}

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
          renderInspectorContent={(cls) => (
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
      <PageHeader
        eyebrow="Schema"
        title="Classes"
        idChip="/schema/classes"
        actions={
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="class-add-button"
          >
            + New class
          </Button>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="classes" onSelectTab={handleTabNavigate} />

      <div data-testid="classes-content">
        <ClassesPageContent
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
        title="Create Class"
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

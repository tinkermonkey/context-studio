import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  StatTile,
  Panel,
  PageHeader,
  StatGrid,
  ActivityTimeline,
  QuickAccessGrid,
  Button,
  Icon,
  Chip,
  type ActivityEvent,
  type ActivityEventType,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { HierarchyTree } from "@/components/ontology/HierarchyTree";
import { useHealth, useStatsTrends } from "@/api/hooks/admin";
import { useTaxonomies, useSchemes, useClasses, useIndividuals } from "@/api/hooks/ontology";
import { useChanges } from "@/api/hooks/versioning";

export const Route = createFileRoute("/app/")({
  component: Dashboard,
});

function mapOperationToEventType(op: string): ActivityEventType {
  switch (op) {
    case "create":
      return "create";
    case "update":
      return "update";
    case "delete":
      return "delete";
    default:
      return "run";
  }
}

function meaningfulSparkData(data: number[] | undefined): number[] | undefined {
  if (!data || data.length < 2 || data.every((v) => v === 0)) return undefined;
  return data;
}

function entityTypeToKind(entityType: string): { kind: string; kindLabel: string } | undefined {
  const map: Record<string, { kind: string; kindLabel: string }> = {
    taxonomy: { kind: "TAXONOMY", kindLabel: "Taxonomy" },
    class: { kind: "CLASS", kindLabel: "Class" },
    individual: { kind: "INDIVIDUAL", kindLabel: "Individual" },
    relationship: { kind: "RELATIONSHIP", kindLabel: "Relationship" },
    property_definition: { kind: "PROPERTY", kindLabel: "Property" },
    concept_scheme: { kind: "CONCEPT_SCHEME", kindLabel: "Concept Scheme" },
  };
  return (
    map[entityType] ?? { kind: entityType.toUpperCase(), kindLabel: entityType.replace(/_/g, " ") }
  );
}

function EmptyState() {
  const navigate = useNavigate();
  return (
    <div className="empty-state">
      <Icon name="schema" size={48} />
      <div className="empty-state-content">
        <div className="empty-state-title">Welcome to Context Studio</div>
        <div className="empty-state-description">Start building your knowledge graph</div>
      </div>
      <div
        className="row"
        style={{ gap: "var(--space-3)", flexWrap: "wrap", justifyContent: "center" }}
      >
        <Button variant="ghost" onClick={() => navigate({ to: "/app/schema/taxonomies" })}>
          <Icon name="plus" size={14} /> Create taxonomy
        </Button>
        <Button variant="ghost" onClick={() => navigate({ to: "/app/reference/sources" })}>
          <Icon name="link" size={14} /> Import data
        </Button>
      </div>
    </div>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const { data: health } = useHealth();
  const { data: trends } = useStatsTrends();
  const {
    data: taxonomies,
    isLoading: taxonomiesLoading,
    error: taxonomiesError,
    refetch: refetchTaxonomies,
  } = useTaxonomies();
  const { data: schemes, isLoading: schemesLoading } = useSchemes();
  const {
    data: classes,
    isLoading: classesLoading,
    error: classesError,
    refetch: refetchClasses,
  } = useClasses();
  const { data: individuals, isLoading: individualsLoading } = useIndividuals();
  const {
    data: changesData,
    isLoading: changesLoading,
    error: changesError,
    refetch: refetchChanges,
  } = useChanges({ limit: 10 });

  const taxonomyCount = taxonomies?.total ?? 0;
  const schemeCount = schemes?.total ?? 0;
  const classCount = classes?.total ?? 0;
  const individualCount = individuals?.total ?? 0;
  const isEmptyState = !taxonomiesLoading && !taxonomiesError && taxonomyCount === 0;

  if (isEmptyState) {
    return (
      <div>
        <div className="cs-page-meta">
          <Chip variant="amber">workspace · local</Chip>
        </div>
        <PageHeader title="Dashboard" />
        <EmptyState />
      </div>
    );
  }

  const activityEvents: ActivityEvent[] =
    !changesError && changesData?.events
      ? changesData.events.slice(0, 8).map((event) => {
          const stateTitle =
            (typeof event.new_state?.title === "string" && event.new_state.title) ||
            (typeof event.new_state?.name === "string" && event.new_state.name) ||
            (typeof event.new_state?.label === "string" && event.new_state.label) ||
            `Unnamed ${event.entity_type.replace(/_/g, " ")}`;
          const kindProps = entityTypeToKind(event.entity_type);
          return {
            id: event.id,
            type: mapOperationToEventType(event.operation),
            subject: stateTitle,
            timestamp: event.timestamp,
            ...kindProps,
          };
        })
      : [];

  const isDaemonHealthy = health?.status === "healthy";

  return (
    <div>
      {/* Page meta row */}
      <div className="cs-page-meta">
        <Chip variant="amber">workspace · local</Chip>
        <span className="cs-page-meta__sep">·</span>
        <span className={isDaemonHealthy ? "cs-page-meta__health" : undefined}>
          {isDaemonHealthy ? "graph daemon healthy" : "graph daemon unavailable"}
        </span>
      </div>

      <PageHeader
        title="Dashboard"
        idChip="/workspace/local"
        subtitle="Curate knowledge graphs for retrieval-augmented generation and agents. Taxonomies group concept schemes; concept schemes hold classes; classes hold individuals."
        actions={
          <>
            <Button variant="ghost" onClick={() => window.location.reload()}>
              <Icon name="reload" size={13} /> Refresh
            </Button>
          </>
        }
      />

      <div style={{ height: 18 }} />

      {/* Stat grid */}
      <ErrorBanner
        error={taxonomiesError}
        onRetry={refetchTaxonomies}
        message="Could not load taxonomies"
        compact
      />
      <StatGrid columns={3}>
        <StatTile
          label="Taxonomies"
          value={taxonomiesLoading ? "—" : String(taxonomyCount)}
          color="cyan"
          icon="schema"
          meta={taxonomiesLoading ? undefined : `${taxonomyCount} active`}
          sparkData={meaningfulSparkData(trends?.taxonomies)}
        />
        <StatTile
          label="Classes"
          value={classesLoading ? "—" : String(classCount)}
          color="violet"
          icon="schema"
          sparkData={meaningfulSparkData(trends?.classes)}
        />
        <StatTile
          label="Individuals"
          value={individualsLoading ? "—" : String(individualCount)}
          color="emerald"
          icon="data"
          sparkData={meaningfulSparkData(trends?.individuals)}
        />
      </StatGrid>

      <div style={{ height: 18 }} />

      {/* Hierarchy + Activity */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 14 }}>
        {/* Knowledge Graph Structure */}
        <Panel
          title="Knowledge graph structure"
          headerAction={
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "rgb(var(--canvas-fg-3))",
                  whiteSpace: "nowrap",
                }}
              >
                {taxonomyCount} tax · {schemeCount} sch · {classCount} cls
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate({ to: "/app/schema/classes" })}
              >
                Open <Icon name="arrowRight" size={11} />
              </Button>
            </div>
          }
          noPadding
        >
          <ErrorBanner
            error={classesError}
            onRetry={refetchClasses}
            message="Could not load class hierarchy"
            compact
          />
          <div style={{ maxHeight: 460, overflow: "auto", padding: "6px 0" }}>
            {!classesError && (
              <HierarchyTree
                taxonomies={taxonomies?.items}
                schemes={schemes?.items}
                classes={classes?.items}
                loading={taxonomiesLoading || schemesLoading || classesLoading}
                error={classesError}
              />
            )}
          </div>
        </Panel>

        {/* Recent Activity */}
        <Panel
          title="Recent activity"
          headerAction={
            <Button variant="ghost" size="sm">
              View all
            </Button>
          }
          noPadding
        >
          <ErrorBanner
            error={changesError}
            onRetry={refetchChanges}
            message="Could not load recent changes"
            compact
          />
          <div style={{ padding: "4px 4px 8px" }}>
            {!changesError && (
              <>
                {changesLoading ? (
                  <div className="stack-lg">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div
                        key={i}
                        className="skeleton"
                        style={{ height: "36px", borderRadius: "var(--radius-md, 6px)" }}
                      />
                    ))}
                  </div>
                ) : (
                  <ActivityTimeline events={activityEvents} emptyState="No recent changes." />
                )}
              </>
            )}
          </div>
        </Panel>
      </div>

      <div style={{ height: 24 }} />

      {/* Quick Access */}
      <div className="cs-between" style={{ marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "rgb(var(--canvas-fg-1))" }}>
          Quick access
        </h3>
        <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12 }}>
          Jump to common workflows
        </span>
      </div>
      <QuickAccessGrid
        tiles={[
          {
            id: "tax",
            icon: "schema",
            title: "Taxonomies",
            description: "Manage top-level domains and concept schemes",
          },
          {
            id: "cls",
            icon: "graph",
            title: "Classes",
            description: "Define the structure of your knowledge",
          },
          {
            id: "prop",
            icon: "component",
            title: "Properties",
            description: "Object and literal property definitions",
          },
          {
            id: "ind",
            icon: "data",
            title: "Individuals",
            description: "Browse instances populated from sources",
          },
          {
            id: "ref",
            icon: "link",
            title: "Reference sources",
            description: "External APIs and document corpora",
          },
        ]}
        onAction={(id) => {
          const routes: Record<string, string> = {
            tax: "/app/schema/taxonomies",
            cls: "/app/schema/classes",
            prop: "/app/schema/properties",
            ind: "/app/data/individuals",
            ref: "/app/reference/sources",
          };
          const to = routes[id];
          if (to) navigate({ to });
        }}
      />
    </div>
  );
}

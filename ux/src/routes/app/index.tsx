import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Network, Layers, GitBranch, Cpu, Plus } from "lucide-react";
import {
  StatTile,
  Panel,
  PageHeader,
  KVGrid,
  StatGrid,
  ActivityTimeline,
  QuickAccessGrid,
  type ActivityEvent,
  type ActivityEventType,
} from "@tinkermonkey/heimdall-ui";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { HierarchyTree } from "@/components/ontology/HierarchyTree";
import { PipelineCard } from "@/components/pipeline/PipelineCard";
import { useHealth } from "@/api/hooks/admin";
import { useTaxonomies } from "@/api/hooks/ontology";
import { useClasses } from "@/api/hooks/ontology";
import { useIndividuals } from "@/api/hooks/ontology";
import { usePipelines } from "@/api/hooks/pipeline";
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

function EmptyState() {
  return (
    <div className="empty-state">
      <Network size={48} style={{ color: "var(--canvas-fg-3)" }} />
      <div className="empty-state-content">
        <div className="empty-state-title">Welcome to Context Studio</div>
        <div className="empty-state-description">Start building your knowledge graph</div>
      </div>
      <div
        className="row"
        style={{ gap: "var(--space-3)", flexWrap: "wrap", justifyContent: "center" }}
      >
        <Link to="/app/schema/taxonomies">
          <button className="btn btn-ghost">
            <Plus size={14} />
            Create taxonomy
          </button>
        </Link>
        <Link to="/app/pipelines">
          <button className="btn btn-ghost">
            <Cpu size={14} />
            Run pipeline
          </button>
        </Link>
        <Link to="/app/reference/sources">
          <button className="btn btn-ghost">
            <GitBranch size={14} />
            Import data
          </button>
        </Link>
      </div>
    </div>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const { data: health } = useHealth();
  const {
    data: taxonomies,
    isLoading: taxonomiesLoading,
    error: taxonomiesError,
    refetch: refetchTaxonomies,
  } = useTaxonomies();
  const {
    data: classes,
    isLoading: classesLoading,
    error: classesError,
    refetch: refetchClasses,
  } = useClasses();
  const {
    data: individuals,
    isLoading: individualsLoading,
    error: individualsError,
    refetch: refetchIndividuals,
  } = useIndividuals();
  const {
    data: pipelines,
    isLoading: pipelinesLoading,
    error: pipelinesError,
    refetch: refetchPipelines,
  } = usePipelines();
  const {
    data: changesData,
    isLoading: changesLoading,
    error: changesError,
    refetch: refetchChanges,
  } = useChanges({ limit: 10 });

  const taxonomyCount = taxonomies?.total ?? 0;
  const classCount = classes?.total ?? 0;
  const individualCount = individuals?.total ?? 0;
  const pipelineCount = pipelines?.length ?? 0;
  const isEmptyState = !taxonomiesLoading && !taxonomiesError && taxonomyCount === 0;

  if (isEmptyState) {
    return (
      <div>
        <PageHeader eyebrow="Main" title="Dashboard" idChip="/" />
        <EmptyState />
      </div>
    );
  }

  const activityEvents: ActivityEvent[] =
    !changesError && changesData?.events
      ? changesData.events.slice(0, 8).map((event) => {
          const stateTitle =
            typeof event.new_state?.title === "string" ? event.new_state.title : event.entity_id;
          return {
            id: event.id,
            type: mapOperationToEventType(event.operation),
            subject: `${event.operation} ${event.entity_type}: ${stateTitle}`,
            timestamp: event.timestamp,
          };
        })
      : [];

  return (
    <div>
      <PageHeader eyebrow="Main" title="Dashboard" idChip="/" />

      {/* Stat grid */}
      <ErrorBanner
        error={taxonomiesError}
        onRetry={refetchTaxonomies}
        message="Could not load taxonomies"
        compact
      />
      <StatGrid
        style={{
          marginBottom: "var(--space-6)",
          marginTop: taxonomiesError ? "var(--space-4)" : 0,
        }}
      >
        <StatTile
          label="Taxonomies"
          value={taxonomiesLoading ? "—" : String(taxonomyCount)}
          color="cyan"
        />
        <StatTile
          label="Classes"
          value={classesLoading ? "—" : String(classCount)}
          color="violet"
        />
        <StatTile
          label="Individuals"
          value={individualsLoading ? "—" : String(individualCount)}
          color="amber"
        />
        <StatTile
          label="Pipelines"
          value={pipelinesLoading ? "—" : String(pipelineCount)}
          color="emerald"
        />
      </StatGrid>

      {/* Two-column layout */}
      <div className="grid grid-cols-2 gap-6" style={{ marginBottom: "var(--space-6)" }}>
        {/* Recent Activity */}
        <Panel title="Recent Activity">
          <ErrorBanner
            error={changesError}
            onRetry={refetchChanges}
            message="Could not load recent changes"
            compact
          />
          {!changesError && (
            <>
              {changesLoading ? (
                <div className="stack-lg">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton
                      key={i}
                      height="36px"
                      style={{ borderRadius: "var(--radius-md, 6px)" }}
                    />
                  ))}
                </div>
              ) : (
                <ActivityTimeline events={activityEvents} emptyState="No recent changes." />
              )}
            </>
          )}
        </Panel>

        {/* Graph Health / Quick Stats */}
        <Panel title="System Status">
          {!health ? (
            <div className="stack-lg">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} height="20px" />
              ))}
            </div>
          ) : (
            <KVGrid
              rows={[
                { key: "Status", value: health.status },
                { key: "Database", value: health.database_connected ? "connected" : "unavailable" },
                { key: "NLP pipeline", value: health.nlp_pipeline_ready ? "ready" : "not loaded" },
                { key: "Embedding model", value: health.embedding_model_loaded ? "loaded" : "not loaded" },
                { key: "LLM providers", value: (health.llm_providers_available ?? []).join(", ") || "none" },
                { key: "Uptime", value: `${Math.floor(health.uptime_seconds / 60)}m` },
              ]}
            />
          )}
        </Panel>
      </div>

      {/* Knowledge Graph Structure */}
      <div className="grid grid-cols-2 gap-6" style={{ marginBottom: "var(--space-6)" }}>
        <Panel title="Knowledge Graph Structure">
          <ErrorBanner
            error={classesError}
            onRetry={refetchClasses}
            message="Could not load class hierarchy"
            compact
          />
          {!classesError && (
            <HierarchyTree classes={classes?.items} loading={classesLoading} error={classesError} />
          )}
        </Panel>

        <Panel title="Individuals by Class">
          <ErrorBanner
            error={individualsError}
            onRetry={refetchIndividuals}
            message="Could not load individuals"
            compact
          />
          {!individualsError && individualsLoading && (
            <div className="stack-lg">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} height="28px" style={{ borderRadius: "var(--radius-md, 6px)" }} />
              ))}
            </div>
          )}
          {!individualsError && !individualsLoading && individualCount === 0 && (
            <p style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg-3)", margin: 0 }}>
              No individuals yet.
            </p>
          )}
          {!individualsError &&
            !individualsLoading &&
            individuals &&
            individuals.items.length > 0 && (
              <div style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}>
                Showing {Math.min(individuals.items.length, 10)} of {individuals.total} individuals
              </div>
            )}
        </Panel>
      </div>

      {/* Active Pipelines */}
      <div style={{ marginBottom: "var(--space-6)" }}>
        <ErrorBanner
          error={pipelinesError}
          onRetry={refetchPipelines}
          message="Could not load pipelines"
          compact
        />
        {!pipelinesError && !pipelinesLoading && pipelines && pipelines.length > 0 && (
          <div>
            <div className="flex-row-center" style={{ marginBottom: "var(--space-4)" }}>
              <Layers size={16} style={{ color: "var(--canvas-fg-3)" }} />
              <span
                style={{
                  fontSize: "var(--text-sm)",
                  fontWeight: 600,
                  color: "rgb(var(--canvas-fg-1))",
                }}
              >
                Active Pipelines
              </span>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                gap: "var(--space-4)",
              }}
            >
              {pipelines
                .filter((p) => p.enabled)
                .map((pipeline) => (
                  <PipelineCard key={pipeline.id} pipeline={pipeline} />
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Quick Access */}
      <QuickAccessGrid
        tiles={[
          { id: "schema", icon: "schema", title: "Schema", description: "Manage taxonomies, classes, and properties" },
          { id: "pipelines", icon: "pipeline", title: "Pipelines", description: "Configure and run extraction pipelines" },
          { id: "data", icon: "data", title: "Data", description: "Browse individuals and datasets" },
          { id: "graph", icon: "graph", title: "Graph", description: "Explore the knowledge graph visually" },
        ]}
        onAction={(tileId) => {
          const routes: Record<string, string> = {
            schema: "/app/schema/taxonomies",
            pipelines: "/app/pipelines",
            data: "/app/data/individuals",
            graph: "/app/graph",
          };
          const to = routes[tileId];
          if (to) navigate({ to });
        }}
        columns={4}
      />
    </div>
  );
}

import { createFileRoute, Link } from "@tanstack/react-router";
import { Network, Layers, GitBranch, Cpu, Plus } from "lucide-react";
import { StatTile } from "@/components/ui/StatTile";
import { Panel } from "@/components/ui/Panel";
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
import { formatRelativeTime } from "@/utils/formatters";

export const Route = createFileRoute("/app/")({
  component: Dashboard,
});

function changeOperationColor(op: string): string {
  switch (op) {
    case "create":
      return "#22D3EE";
    case "update":
      return "#A78BFA";
    case "delete":
      return "#F87171";
    default:
      return "var(--canvas-fg-3)";
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

function Dashboard() {
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
        <div className="page-head">
          <div>
            <h1>Dashboard</h1>
            <p className="subtitle">Knowledge graph overview</p>
          </div>
        </div>
        <EmptyState />
      </div>
    );
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p className="subtitle">Knowledge graph overview</p>
        </div>
      </div>

      {/* Stat grid */}
      <ErrorBanner
        error={taxonomiesError}
        onRetry={refetchTaxonomies}
        message="Could not load taxonomies"
        compact
      />
      <div
        className="stat-grid"
        style={{
          marginBottom: "var(--space-6)",
          marginTop: taxonomiesError ? "var(--space-4)" : 0,
        }}
      >
        <StatTile
          label="Taxonomies"
          value={
            taxonomiesLoading ? <Skeleton width={40} height="1.5rem" /> : String(taxonomyCount)
          }
          color="cyan"
          sub="knowledge domains"
        />
        <StatTile
          label="Classes"
          value={classesLoading ? <Skeleton width={40} height="1.5rem" /> : String(classCount)}
          color="violet"
          sub="concept types"
        />
        <StatTile
          label="Individuals"
          value={
            individualsLoading ? <Skeleton width={40} height="1.5rem" /> : String(individualCount)
          }
          color="amber"
          sub="indexed instances"
        />
        <StatTile
          label="Pipelines"
          value={pipelinesLoading ? <Skeleton width={40} height="1.5rem" /> : String(pipelineCount)}
          color="emerald"
          sub={`${pipelines?.filter((p) => p.enabled).length ?? 0} enabled`}
        />
      </div>

      {/* Two-column layout */}
      <div className="grid-2" style={{ marginBottom: "var(--space-6)" }}>
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
              ) : !changesData?.events.length ? (
                <p style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg-3)", margin: 0 }}>
                  No recent changes.
                </p>
              ) : (
                <div className="activity-list">
                  {changesData.events.slice(0, 8).map((event) => {
                    const stateTitle =
                      typeof event.new_state?.title === "string"
                        ? event.new_state.title
                        : event.entity_id;
                    return (
                      <div key={event.id} className="activity-item">
                        <span
                          className="activity-dot"
                          style={{ background: changeOperationColor(event.operation) }}
                        />
                        <div>
                          <div style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg)" }}>
                            {event.operation} {event.entity_type}
                          </div>
                          <div
                            style={{
                              fontSize: "var(--text-xs)",
                              color: "var(--canvas-fg-3)",
                              fontFamily: "var(--mono)",
                            }}
                          >
                            {stateTitle} · {formatRelativeTime(event.timestamp)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
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
            <div
              className="kv"
              style={{
                display: "grid",
                gridTemplateColumns: "140px 1fr",
                gap: "8px 16px",
                alignItems: "center",
              }}
            >
              {(
                [
                  ["Status", health.status],
                  ["Database", health.database_connected ? "connected" : "unavailable"],
                  ["NLP pipeline", health.nlp_pipeline_ready ? "ready" : "not loaded"],
                  ["Embedding model", health.embedding_model_loaded ? "loaded" : "not loaded"],
                  ["LLM providers", (health.llm_providers_available ?? []).join(", ") || "none"],
                  ["Uptime", `${Math.floor(health.uptime_seconds / 60)}m`],
                ] as [string, string][]
              ).map(([k, v]) => (
                <>
                  <dt
                    key={`${k}-k`}
                    style={{
                      fontFamily: "var(--mono)",
                      fontSize: "11px",
                      color: "var(--canvas-fg-3)",
                      textTransform: "uppercase",
                      letterSpacing: "0.07em",
                      margin: 0,
                    }}
                  >
                    {k}
                  </dt>
                  <dd
                    key={`${k}-v`}
                    style={{
                      margin: 0,
                      fontFamily: "var(--mono)",
                      fontSize: "13px",
                      color:
                        v === "connected" || v === "ready" || v === "loaded"
                          ? "var(--accent-emerald, #10b981)"
                          : v === "unavailable" || v === "not loaded"
                            ? "var(--rose-400, #fb7185)"
                            : "var(--canvas-fg)",
                    }}
                  >
                    {v}
                  </dd>
                </>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {/* Knowledge Graph Structure */}
      <div className="grid-2" style={{ marginBottom: "var(--space-6)" }}>
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
      <div>
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
                  color: "var(--canvas-fg)",
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
    </div>
  );
}

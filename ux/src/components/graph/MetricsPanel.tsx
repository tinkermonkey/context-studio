import { useGraphMetrics } from "@/api/hooks/graph";
import type { components } from "@/api/types";
import { Panel } from "@/components/ui/Panel";
import { StatTile } from "@/components/ui/StatTile";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

type GraphMetricsResponse = components["schemas"]["GraphMetricsResponse"];

export function MetricsPanel() {
  const { data, isLoading, error, refetch } = useGraphMetrics();

  const renderLoadingState = () => (
    <div className="metrics-grid">
      <div className="stat" data-color="cyan">
        <div className="label">Node Count</div>
        <Skeleton width={40} height="1.5rem" />
      </div>
      <div className="stat" data-color="violet">
        <div className="label">Edge Count</div>
        <Skeleton width={40} height="1.5rem" />
      </div>
      <div className="stat" data-color="amber">
        <div className="label">Communities</div>
        <Skeleton width={40} height="1.5rem" />
      </div>
      <div className="stat" data-color="emerald">
        <div className="label">Avg Degree</div>
        <Skeleton width={40} height="1.5rem" />
      </div>

      <div style={{ gridColumn: "1 / -1", marginTop: "1rem" }}>
        <div style={{ fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.5rem" }}>
          Top Centrality
        </div>
        {[...Array(5)].map((_, i) => (
          <div key={i} style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <Skeleton width={100} height="1.25rem" />
            <Skeleton width={40} height="1.25rem" />
          </div>
        ))}
      </div>
    </div>
  );

  const renderEmptyState = () => (
    <div
      style={{
        textAlign: "center",
        padding: "2rem 1rem",
        color: "var(--text-secondary)",
      }}
    >
      <p>Build the graph to see metrics</p>
    </div>
  );

  const renderPopulatedState = (metrics: GraphMetricsResponse) => {
    const nodeCount = Object.keys(metrics.centrality).length;
    const edgeCount = Object.values(metrics.degree_distribution).reduce((a, b) => a + b, 0) / 2;
    const communityCount = metrics.communities.length;

    const centralityEntries = Object.entries(metrics.centrality).sort(([, a], [, b]) => b - a);
    const topCentralityNodes = centralityEntries.slice(0, 10);

    const maxDegree = Math.max(...Object.values(metrics.degree_distribution));
    const degreeDistributionEntries = Object.entries(metrics.degree_distribution)
      .map(([degree, count]) => ({ degree: parseInt(degree, 10), count }))
      .sort((a, b) => a.degree - b.degree);

    return (
      <div className="metrics-grid">
        <div data-testid="graph-metrics-node-count">
          <StatTile label="Node Count" value={nodeCount.toString()} color="cyan" />
        </div>
        <div data-testid="graph-metrics-edge-count">
          <StatTile label="Edge Count" value={Math.round(edgeCount).toString()} color="violet" />
        </div>
        <div data-testid="graph-metrics-community-count">
          <StatTile
            label="Communities"
            value={communityCount.toString()}
            color="amber"
            sub={`${metrics.algorithm}`}
          />
        </div>
        <div data-testid="graph-metrics-avg-degree">
          <StatTile
            label="Avg Degree"
            value={metrics.average_degree.toFixed(2)}
            color="emerald"
            sub="betweenness"
          />
        </div>

        {topCentralityNodes.length > 0 && (
          <div
            style={{
              gridColumn: "1 / -1",
              marginTop: "1rem",
            }}
          >
            <div style={{ fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.75rem" }}>
              Top Centrality Nodes
            </div>
            <div
              data-testid="graph-metrics-centrality-list"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.5rem",
              }}
            >
              {topCentralityNodes.map(([nodeId, score], index) => (
                <div
                  key={nodeId}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "0.5rem",
                    borderRadius: "var(--radius-sm, 4px)",
                    background: "var(--canvas-bg-tertiary)",
                    fontSize: "0.75rem",
                  }}
                >
                  <span
                    style={{
                      fontWeight: 500,
                      color: "var(--text-secondary)",
                      minWidth: "24px",
                    }}
                  >
                    {index + 1}.
                  </span>
                  <span
                    style={{
                      flex: 1,
                      fontFamily: "var(--mono)",
                      fontSize: "0.6875rem",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      marginLeft: "0.5rem",
                    }}
                    title={nodeId}
                  >
                    {nodeId}
                  </span>
                  <span
                    style={{
                      fontWeight: 500,
                      color: "var(--cyan-600)",
                      marginLeft: "0.5rem",
                    }}
                  >
                    {score.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {degreeDistributionEntries.length > 0 && (
          <div
            style={{
              gridColumn: "1 / -1",
              marginTop: "1rem",
            }}
          >
            <div style={{ fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.75rem" }}>
              Degree Distribution
            </div>
            <div
              data-testid="graph-metrics-degree-distribution"
              style={{
                display: "flex",
                alignItems: "flex-end",
                gap: "0.25rem",
                height: "120px",
                padding: "0.5rem 0",
              }}
            >
              {degreeDistributionEntries.map(({ degree, count }) => (
                <div
                  key={degree}
                  style={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "0.25rem",
                  }}
                >
                  <div
                    style={{
                      width: "100%",
                      height: `${(count / maxDegree) * 100}px`,
                      background: "var(--violet-500)",
                      borderRadius: "var(--radius-sm, 4px)",
                      minHeight: "2px",
                    }}
                    title={`Degree ${degree}: ${count} nodes`}
                  />
                  <span
                    style={{
                      fontSize: "0.5rem",
                      color: "var(--text-secondary)",
                      whiteSpace: "nowrap",
                      textAnchor: "middle",
                    }}
                  >
                    {degree}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div data-testid="graph-metrics-panel">
      <Panel title="Graph Metrics" className="metrics-panel">
        {error && (
          <ErrorBanner
            error={error as Error}
            onRetry={() => refetch()}
            message="Failed to load metrics"
            compact
          />
        )}

        {isLoading ? (
          renderLoadingState()
        ) : !data || Object.keys(data.centrality).length === 0 ? (
          renderEmptyState()
        ) : (
          renderPopulatedState(data)
        )}
      </Panel>
    </div>
  );
}

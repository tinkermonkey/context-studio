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
    <div className="panel-body">
      <div className="grid-2">
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
      </div>

      <div className="metrics-section">
        <div className="metrics-section-title">
          Top Centrality
        </div>
        <div className="centrality-list-skeleton">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="centrality-row-skeleton">
              <Skeleton width={100} height="1.25rem" />
              <Skeleton width={40} height="1.25rem" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderEmptyState = () => (
    <div className="metrics-empty-state">
      <p>Build the graph to see metrics</p>
    </div>
  );

  const renderPopulatedState = (metrics: GraphMetricsResponse) => {
    const nodeCount = Object.keys(metrics.centrality).length;
    const edgeCount = Object.values(metrics.degree_distribution).reduce((a, b) => a + b, 0) / 2;
    const communityCount = metrics.communities.length;

    const centralityEntries = Object.entries(metrics.centrality).sort(([, a], [, b]) => b - a);
    const topCentralityNodes = centralityEntries.slice(0, 10);

    // Aggregate degree_distribution (node_id → degree) into histogram (degree → count)
    const degreeHistogram: Record<number, number> = {};
    Object.entries(metrics.degree_distribution).forEach(([, degree]) => {
      const d = degree as number;
      degreeHistogram[d] = (degreeHistogram[d] || 0) + 1;
    });

    const degreeDistributionEntries = Object.entries(degreeHistogram)
      .map(([degree, count]) => ({ degree: parseInt(degree, 10), count }))
      .sort((a, b) => a.degree - b.degree);

    const maxDegree = degreeDistributionEntries.length > 0
      ? Math.max(...degreeDistributionEntries.map(e => e.count))
      : 0;

    return (
      <div className="panel-body">
        <div className="grid-2">
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
              sub={metrics.algorithm}
            />
          </div>
          <div data-testid="graph-metrics-avg-degree">
            <StatTile
              label="Avg Degree"
              value={metrics.average_degree.toFixed(2)}
              color="emerald"
            />
          </div>
        </div>

        {topCentralityNodes.length > 0 && (
          <div className="metrics-section">
            <div className="metrics-section-title">
              Top Centrality Nodes
            </div>
            <div
              data-testid="graph-metrics-centrality-list"
              className="centrality-list"
            >
              {topCentralityNodes.map(([nodeId, score], index) => (
                <div
                  key={nodeId}
                  className="centrality-row"
                >
                  <span className="centrality-index">
                    {index + 1}.
                  </span>
                  <span
                    className="centrality-node-id"
                    title={nodeId}
                  >
                    {nodeId}
                  </span>
                  <span className="centrality-score">
                    {score.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {degreeDistributionEntries.length > 0 && (
          <div className="metrics-section">
            <div className="metrics-section-title">
              Degree Distribution
            </div>
            <div
              data-testid="graph-metrics-degree-distribution"
              className="degree-chart"
            >
              {degreeDistributionEntries.map(({ degree, count }) => (
                <div
                  key={degree}
                  className="degree-bar-container"
                >
                  <div
                    className="degree-bar"
                    style={{
                      height: `${(count / maxDegree) * 100}px`,
                    }}
                    title={`Degree ${degree}: ${count} nodes`}
                  />
                  <span className="degree-label">
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
    <div data-testid="graph-metrics-panel" id="panel-metrics">
      <Panel title="Graph Metrics">
        {error && !isLoading && !data ? (
          <div className="panel-body">
            <ErrorBanner
              error={error as Error}
              onRetry={() => refetch()}
              message="Failed to load metrics"
              compact
            />
          </div>
        ) : isLoading ? (
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

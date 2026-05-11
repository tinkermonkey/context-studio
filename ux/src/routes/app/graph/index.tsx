import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RotateCw, Network } from "lucide-react";
import { useGraphVisualization } from "@/api/hooks/graph";
import { GraphCanvasComponent } from "@/components/graph/GraphCanvas";
import { MetricsPanel } from "@/components/graph/MetricsPanel";
import { PathFinder } from "@/components/graph/PathFinder";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs } from "@/components/ui/Tabs";
import "@/design-system/graph.css";

export const Route = createFileRoute("/app/graph/")({
  component: GraphPage,
});

function GraphPage() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>();
  const [activeTab, setActiveTab] = useState<string>("metrics");
  const graphVisualization = useGraphVisualization();

  const isLoading = graphVisualization.isPending;
  const error = graphVisualization.error;
  const data = graphVisualization.data;

  const hasData = data && data.nodes.length > 0;

  return (
    <div data-testid="graph-page">
      <div className="page-head">
        <div>
          <h1>Graph Visualization</h1>
          <p className="subtitle">Explore your knowledge graph</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => graphVisualization.mutate()}
          disabled={isLoading}
          aria-busy={isLoading}
        >
          {isLoading ? (
            <>
              <RotateCw size={16} className="animate-spin" />
              Building...
            </>
          ) : (
            <>
              <RotateCw size={16} />
              Build Graph
            </>
          )}
        </button>
      </div>

      {error && (
        <ErrorBanner
          error={error as Error}
          onRetry={() => graphVisualization.mutate()}
          message="Failed to build graph"
        />
      )}

      {isLoading && !hasData && (
        <div className="graph-shell">
          <Skeleton width="100%" height="100%" className="graph-canvas" />
          <Skeleton width="100%" height="100%" className="graph-inspector" />
        </div>
      )}

      {!isLoading && !hasData && !error && (
        <EmptyState
          icon={<Network size={48} />}
          title="No graph data"
          description="Build a graph to visualize your knowledge base"
          action={{
            label: "Build Graph",
            onClick: () => graphVisualization.mutate(),
          }}
        />
      )}

      {hasData && (
        <div className="graph-shell">
          <GraphCanvasComponent
            nodes={data.nodes}
            edges={data.edges}
            onNodeClick={setSelectedNodeId}
            selectedNodeId={selectedNodeId}
          />
          <aside className="graph-inspector" role="complementary" aria-label="Inspector panel">
            <Tabs
              tabs={[
                { id: "metrics", label: "Metrics" },
                { id: "path", label: "Path Finder" },
                { id: "node", label: "Node Inspector" },
              ]}
              active={activeTab}
              onChange={setActiveTab}
            />
            {activeTab === "metrics" ? (
              <MetricsPanel />
            ) : activeTab === "path" ? (
              <div className="panel" id="panel-path" style={{ padding: "14px 16px", overflowY: "auto" }}>
                <PathFinder onNodeSelect={setSelectedNodeId} />
              </div>
            ) : (
              <div className="panel" id="panel-node">
                {selectedNodeId ? (
                  <div>
                    <div className="gi-head">
                      <div className="gi-title">{selectedNodeId}</div>
                      <div className="gi-id">Node ID</div>
                    </div>
                    <div className="gi-body">
                      <p className="gi-desc">Selected node details</p>
                    </div>
                  </div>
                ) : (
                  <div className="empty">No node selected</div>
                )}
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

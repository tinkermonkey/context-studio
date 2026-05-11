import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RotateCw, Network } from "lucide-react";
import { useGraphVisualization } from "@/api/hooks/graph";
import { GraphCanvasComponent } from "@/components/graph/GraphCanvas";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import "@/design-system/graph.css";

export const Route = createFileRoute("/app/graph/")({
  component: GraphPage,
});

function GraphPage() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>();
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
          <div className="graph-canvas" style={{ background: "#f0f0f0" }}>
            <div
              style={{
                width: "100%",
                height: "100%",
                background: "linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%)",
                backgroundSize: "200% 100%",
                animation: "pulse 1.5s infinite",
              }}
            />
          </div>
          <div className="graph-inspector" />
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
          <div className="graph-inspector">
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
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% {
            background-position: 200% 0;
          }
          50% {
            background-position: 0 0;
          }
        }
      `}</style>
    </div>
  );
}

import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RotateCw, Network } from "lucide-react";
import { useGraphVisualization } from "@/api/hooks/graph";
import { GraphCanvasComponent } from "@/components/graph/GraphCanvas";
import { MetricsPanel } from "@/components/graph/MetricsPanel";
import { PathFinder } from "@/components/graph/PathFinder";
import { SparqlEditor } from "@/components/graph/SparqlEditor";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { TabBar, Button, GraphInspector } from "@tinkermonkey/heimdall-ui";
import { COPY } from "./-copy";
import "@/design-system/graph.css";

export const Route = createFileRoute("/app/graph/")({
  component: GraphPage,
});

export function GraphPage() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>();
  const [activeTab, setActiveTab] = useState<string>("metrics");
  const graphVisualization = useGraphVisualization();

  const isLoading = graphVisualization.isPending;
  const error = graphVisualization.error;
  const data = graphVisualization.data;

  const hasData = data && data.nodes.length > 0;

  return (
    <div data-testid="graph-page">
      <PageHeader
        eyebrow="Knowledge Graph"
        title={COPY.PAGE_TITLE}
        subtitle={COPY.PAGE_SUBTITLE}
        actions={
          <Button
            variant="primary"
            size="md"
            onClick={() => graphVisualization.mutate()}
            disabled={isLoading}
            aria-busy={isLoading}
            data-testid="build-graph-button"
          >
            {isLoading ? (
              <>
                <RotateCw size={16} className="animate-spin" />
                {COPY.BUILDING_GRAPH_BUTTON}
              </>
            ) : (
              <>
                <RotateCw size={16} />
                {COPY.BUILD_GRAPH_BUTTON}
              </>
            )}
          </Button>
        }
      />

      {error && (
        <ErrorBanner
          error={error as Error}
          onRetry={() => graphVisualization.mutate()}
          message={COPY.ERROR_MESSAGE}
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
          title={COPY.EMPTY_STATE_TITLE}
          description={COPY.EMPTY_STATE_DESCRIPTION}
          action={{
            label: COPY.BUILD_GRAPH_BUTTON,
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
            <TabBar
              tabs={[
                { id: "metrics", label: COPY.METRICS_TAB },
                { id: "path", label: COPY.PATH_FINDER_TAB },
                { id: "sparql", label: COPY.SPARQL_QUERY_TAB },
                { id: "node", label: COPY.NODE_INSPECTOR_TAB },
              ]}
              activeTabId={activeTab}
              onSelectTab={setActiveTab}
            />
            {activeTab === "metrics" ? (
              <MetricsPanel />
            ) : activeTab === "path" ? (
              <div
                className="panel"
                id="panel-path"
                style={{ padding: "14px 16px", overflowY: "auto" }}
              >
                <PathFinder onNodeSelect={setSelectedNodeId} />
              </div>
            ) : activeTab === "sparql" ? (
              <div
                className="panel"
                id="panel-sparql"
                style={{ padding: "14px 16px", overflowY: "auto" }}
              >
                <SparqlEditor />
              </div>
            ) : (
              <div className="panel" id="panel-node">
                <GraphInspector
                  node={
                    selectedNodeId && data
                      ? {
                          id: selectedNodeId,
                          title: selectedNodeId,
                          kind: data.nodes.find((n) => n.id === selectedNodeId)?.kind,
                          description: COPY.SELECTED_NODE_DETAILS,
                        }
                      : null
                  }
                  relationships={[]}
                  onNodeSelect={setSelectedNodeId}
                  emptyStateText={COPY.NO_NODE_SELECTED}
                />
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

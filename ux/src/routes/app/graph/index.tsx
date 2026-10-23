import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RotateCw, Network } from "lucide-react";
import { useBuildGraph, useGraphView } from "@/api/hooks/graph";
import { GraphCanvasComponent } from "@/components/graph/GraphCanvas";
import { GraphLayerToolbar, type GraphFocus } from "@/components/graph/GraphLayerToolbar";
import { GraphNodeInspector } from "@/components/graph/GraphNodeInspector";
import {
  defaultLayerIds,
  defaultNodeKind,
  filterGraphView,
  neighborhood,
  type GraphFilter,
  type GraphLayoutMode,
} from "@/components/graph/graphLayers";
import { MetricsPanel } from "@/components/graph/MetricsPanel";
import { PathFinder } from "@/components/graph/PathFinder";
import { SparqlEditor } from "@/components/graph/SparqlEditor";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToasts } from "@/components/ui/Toast";
import { TabBar, Button, PageHeader, SplitPane } from "@tinkermonkey/heimdall-ui";
import { COPY } from "./-copy";
import "@/design-system/graph.css";

export const Route = createFileRoute("/app/graph/")({
  component: GraphPage,
});

const NODE_TAB = "node";
const GRAPH_SPLIT_PERCENT = 68;
const GRAPH_MIN_WIDTH_PX = 360;
const GRAPH_MAX_WIDTH_PX = 4000;

export function GraphPage() {
  const graphView = useGraphView();
  const buildGraph = useBuildGraph();
  const { toast } = useToasts();

  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>();
  const [activeTab, setActiveTab] = useState<string>(NODE_TAB);
  // null until the user changes the layer selection; falls back to the default subset.
  const [layerIds, setLayerIds] = useState<string[] | null>(null);
  const [classIds, setClassIds] = useState<string[]>([]);
  // null until the user picks a kind; defaults to individuals when the graph has any.
  const [nodeKind, setNodeKind] = useState<GraphFilter["nodeKind"] | null>(null);
  const [layout, setLayout] = useState<GraphLayoutMode>("layered");
  const [focus, setFocus] = useState<GraphFocus | null>(null);

  const view = graphView.data;

  const filter: GraphFilter = useMemo(
    () => ({
      layerIds: layerIds ?? (view ? defaultLayerIds(view) : []),
      classIds,
      nodeKind: nodeKind ?? (view ? defaultNodeKind(view) : "all"),
    }),
    [layerIds, classIds, nodeKind, view],
  );

  const slice = useMemo(() => {
    if (!view) return { nodes: [], edges: [] };
    return focus
      ? neighborhood(view, focus.nodeId, focus.depth, filter.nodeKind)
      : filterGraphView(view, filter);
  }, [view, focus, filter]);

  const focusLabel = focus ? view?.nodes.find((n) => n.id === focus.nodeId)?.label : undefined;

  const selectNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setActiveTab(NODE_TAB);
  };

  const focusOn = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setActiveTab(NODE_TAB);
    setFocus((current) => ({ nodeId, depth: current?.depth ?? 1 }));
  };

  const handleFilterChange = (next: GraphFilter) => {
    setLayerIds(next.layerIds);
    setClassIds(next.classIds);
    setNodeKind(next.nodeKind);
  };

  const handleRebuild = () => {
    buildGraph.mutate(undefined, {
      onError: (error) =>
        toast(
          "error",
          COPY.BUILD_ERROR_TITLE,
          error instanceof Error ? error.message : String(error),
        ),
    });
  };

  const isLoading = graphView.isPending;
  const hasData = Boolean(view && view.nodes.length > 0);

  const inspectorPanel = view && (
    <div
      role="complementary"
      aria-label="Inspector panel"
      className="flex h-full flex-col overflow-hidden"
    >
      <TabBar
        tabs={[
          { id: NODE_TAB, label: COPY.NODE_INSPECTOR_TAB },
          { id: "metrics", label: COPY.METRICS_TAB },
          { id: "path", label: COPY.PATH_FINDER_TAB },
          { id: "sparql", label: COPY.SPARQL_QUERY_TAB },
        ]}
        activeTabId={activeTab}
        onSelectTab={setActiveTab}
      />
      {activeTab === "metrics" ? (
        <MetricsPanel />
      ) : activeTab === "path" ? (
        <div className="flex-1 overflow-y-auto p-3.5 text-[13px]">
          <PathFinder onNodeSelect={selectNode} />
        </div>
      ) : activeTab === "sparql" ? (
        <div className="flex-1 overflow-y-auto p-3.5 text-[13px]">
          <SparqlEditor />
        </div>
      ) : (
        <GraphNodeInspector
          view={view}
          nodeId={selectedNodeId}
          isFocused={focus?.nodeId === selectedNodeId}
          onFocus={focusOn}
          onNavigate={focusOn}
          emptyStateText={COPY.NO_NODE_SELECTED}
        />
      )}
    </div>
  );

  return (
    <div data-testid="graph-page" className="graph-page">
      <PageHeader
        eyebrow="Knowledge Graph"
        title={COPY.PAGE_TITLE}
        idChip="/graph"
        subtitle={COPY.PAGE_DESCRIPTION}
        actions={
          <Button
            variant="secondary"
            onClick={handleRebuild}
            disabled={buildGraph.isPending}
            aria-busy={buildGraph.isPending}
            data-testid="build-graph-button"
          >
            <RotateCw size={16} className={buildGraph.isPending ? "animate-spin" : undefined} />
            {buildGraph.isPending ? COPY.BUILDING_GRAPH_BUTTON : COPY.BUILD_GRAPH_BUTTON}
          </Button>
        }
      />

      {graphView.error && (
        <ErrorBanner
          error={graphView.error as Error}
          onRetry={() => graphView.refetch()}
          message={COPY.ERROR_MESSAGE}
        />
      )}

      {isLoading && (
        <SplitPane
          direction="horizontal"
          data-testid="graph-shell"
          initialSplitPercent={GRAPH_SPLIT_PERCENT}
          maxSize={GRAPH_MAX_WIDTH_PX}
          first={<div className="skeleton graph-page__skeleton" />}
          second={<div className="skeleton graph-page__skeleton" />}
        />
      )}

      {!isLoading && !hasData && !graphView.error && (
        <EmptyState
          icon={<Network size={48} />}
          title={COPY.EMPTY_STATE_TITLE}
          description={COPY.EMPTY_STATE_DESCRIPTION}
        />
      )}

      {view && hasData && (
        <>
          <GraphLayerToolbar
            view={view}
            filter={filter}
            onFilterChange={handleFilterChange}
            layout={layout}
            onLayoutChange={setLayout}
            focus={focus}
            focusLabel={focusLabel}
            onFocusDepthChange={(depth) => setFocus((current) => current && { ...current, depth })}
            onExitFocus={() => setFocus(null)}
            visibleNodeCount={slice.nodes.length}
            visibleEdgeCount={slice.edges.length}
          />
          <SplitPane
            direction="horizontal"
            data-testid="graph-shell"
            initialSplitPercent={GRAPH_SPLIT_PERCENT}
            minSize={GRAPH_MIN_WIDTH_PX}
            maxSize={GRAPH_MAX_WIDTH_PX}
            dividerLabel="Resize graph and inspector"
            first={
              <GraphCanvasComponent
                nodes={slice.nodes}
                edges={slice.edges}
                layers={view.layers}
                layout={layout}
                selectedNodeId={selectedNodeId}
                focusNodeId={focus?.nodeId}
                onNodeSelect={selectNode}
                emptyText={COPY.NO_MATCHING_NODES}
              />
            }
            second={inspectorPanel}
          />
        </>
      )}
    </div>
  );
}

import { useMemo } from "react";
import { X } from "lucide-react";
import { Button, FilterDropdown, SegmentedControl } from "@tinkermonkey/heimdall-ui";
import type { GraphView } from "@/api/hooks/graph";
import {
  FORCE_LAYOUT_MAX_NODES,
  MAX_FOCUS_DEPTH,
  MIN_FOCUS_DEPTH,
  type GraphFilter,
  type GraphLayoutMode,
  type NodeKindFilter,
} from "./graphLayers";

export interface GraphFocus {
  nodeId: string;
  depth: number;
}

interface GraphLayerToolbarProps {
  view: GraphView;
  filter: GraphFilter;
  onFilterChange: (filter: GraphFilter) => void;
  layout: GraphLayoutMode;
  onLayoutChange: (layout: GraphLayoutMode) => void;
  focus: GraphFocus | null;
  focusLabel?: string;
  onFocusDepthChange: (depth: number) => void;
  onExitFocus: () => void;
  visibleNodeCount: number;
  visibleEdgeCount: number;
}

const NODE_KIND_OPTIONS: { value: NodeKindFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "class", label: "Classes" },
  { value: "individual", label: "Individuals" },
];

const DEPTH_OPTIONS = Array.from({ length: MAX_FOCUS_DEPTH - MIN_FOCUS_DEPTH + 1 }, (_, i) => ({
  value: MIN_FOCUS_DEPTH + i,
  label: `${MIN_FOCUS_DEPTH + i} hop${MIN_FOCUS_DEPTH + i === 1 ? "" : "s"}`,
}));

function summarize(selected: string[], titleById: Map<string, string>, emptyText: string): string {
  if (selected.length === 0) return emptyText;
  if (selected.length === 1) return titleById.get(selected[0]) ?? "1 selected";
  return `${selected.length} selected`;
}

/**
 * Filter bar for the layered graph: layer (concept scheme) and class filters,
 * node kind, layout mode, and — while a node is focused — the focus depth and
 * an exit control.
 */
export function GraphLayerToolbar({
  view,
  filter,
  onFilterChange,
  layout,
  onLayoutChange,
  focus,
  focusLabel,
  onFocusDepthChange,
  onExitFocus,
  visibleNodeCount,
  visibleEdgeCount,
}: GraphLayerToolbarProps) {
  const layerTitleById = useMemo(
    () => new Map(view.layers.map((layer) => [layer.id, layer.title])),
    [view.layers],
  );

  const layerSections = useMemo(
    () =>
      view.taxonomies
        .map((taxonomy) => ({
          taxonomy,
          layers: view.layers.filter((layer) => layer.taxonomy_id === taxonomy.id),
        }))
        .filter((section) => section.layers.length > 0)
        // The layered model (most layers, e.g. DR's 12) first.
        .sort((a, b) => b.layers.length - a.layers.length),
    [view.taxonomies, view.layers],
  );

  const classSections = useMemo(() => {
    const selected = new Set(filter.layerIds);
    return view.layers
      .filter((layer) => selected.has(layer.id))
      .map((layer) => ({
        layer,
        classes: view.nodes
          .filter((n) => n.node_type === "class" && n.concept_scheme_id === layer.id)
          .sort((a, b) => a.label.localeCompare(b.label)),
      }))
      .filter((section) => section.classes.length > 0);
  }, [view.layers, view.nodes, filter.layerIds]);

  const classTitleById = useMemo(
    () => new Map(view.nodes.filter((n) => n.node_type === "class").map((n) => [n.id, n.label])),
    [view.nodes],
  );

  const handleLayersChange = (layerIds: string[]) => {
    // Drop class restrictions that fall outside the new layer selection.
    const allowed = new Set(layerIds);
    const classIds = filter.classIds.filter((id) => {
      const node = view.nodes.find((n) => n.id === id);
      return Boolean(node?.concept_scheme_id && allowed.has(node.concept_scheme_id));
    });
    onFilterChange({ ...filter, layerIds, classIds });
  };

  const forceDisabled = visibleNodeCount > FORCE_LAYOUT_MAX_NODES;

  return (
    <div
      className="graph-layer-toolbar"
      data-testid="graph-layer-toolbar"
      role="toolbar"
      aria-label="Graph filters"
    >
      {focus ? (
        <div
          className="graph-layer-toolbar__focus"
          data-testid="graph-focus-bar"
          role="group"
          aria-label="Focus mode"
        >
          <span className="graph-layer-toolbar__eyebrow">Focus</span>
          <span className="graph-layer-toolbar__focus-label" data-testid="graph-focus-label">
            {focusLabel ?? focus.nodeId}
          </span>
          <SegmentedControl
            value={focus.depth}
            onChange={(value) => onFocusDepthChange(Number(value))}
            options={DEPTH_OPTIONS}
            aria-label="Neighborhood depth"
            data-testid="graph-focus-depth"
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={onExitFocus}
            data-testid="graph-focus-exit"
            aria-label="Exit focus mode"
          >
            <X size={14} />
            Exit focus
          </Button>
        </div>
      ) : (
        <>
          <FilterDropdown value={filter.layerIds} onChange={handleLayersChange}>
            <FilterDropdown.Trigger
              label="LAYERS"
              summary={summarize(filter.layerIds, layerTitleById, "None")}
              data-testid="graph-layer-filter"
            />
            <FilterDropdown.Panel
              className="graph-layer-toolbar__panel"
              data-testid="graph-layer-filter-panel"
            >
              {layerSections.map(({ taxonomy, layers }) => (
                <FilterDropdown.Section key={taxonomy.id} title={taxonomy.title.toUpperCase()}>
                  {layers.map((layer) => (
                    <FilterDropdown.Checkbox
                      key={layer.id}
                      value={layer.id}
                      label={layer.title}
                      description={layer.identifier ?? undefined}
                    />
                  ))}
                </FilterDropdown.Section>
              ))}
            </FilterDropdown.Panel>
          </FilterDropdown>

          <FilterDropdown
            value={filter.classIds}
            onChange={(classIds) => onFilterChange({ ...filter, classIds })}
          >
            <FilterDropdown.Trigger
              label="CLASSES"
              summary={summarize(filter.classIds, classTitleById, "All")}
              data-testid="graph-class-filter"
            />
            <FilterDropdown.Panel
              className="graph-layer-toolbar__panel"
              data-testid="graph-class-filter-panel"
            >
              {classSections.map(({ layer, classes }) => (
                <FilterDropdown.Section key={layer.id} title={layer.title.toUpperCase()}>
                  {classes.map((cls) => (
                    <FilterDropdown.Checkbox key={cls.id} value={cls.id} label={cls.label} />
                  ))}
                </FilterDropdown.Section>
              ))}
            </FilterDropdown.Panel>
          </FilterDropdown>
        </>
      )}

      <SegmentedControl
        value={filter.nodeKind}
        onChange={(value) => onFilterChange({ ...filter, nodeKind: value as NodeKindFilter })}
        options={NODE_KIND_OPTIONS}
        aria-label="Node kind"
        data-testid="graph-node-kind-filter"
      />

      <SegmentedControl
        value={layout}
        onChange={(value) => onLayoutChange(value as GraphLayoutMode)}
        options={[
          { value: "layered", label: "Layered" },
          { value: "force", label: "Force", disabled: forceDisabled && layout !== "force" },
        ]}
        aria-label="Layout"
        data-testid="graph-layout-toggle"
      />

      <span
        className="graph-layer-toolbar__counts"
        data-testid="graph-visible-counts"
        role="status"
      >
        {visibleNodeCount} nodes · {visibleEdgeCount} edges
      </span>
    </div>
  );
}

import React, { useRef, useState, useEffect } from "react";
import { Spinner } from "flowbite-react";
import { TreeMenu } from "@/components/graphs/tree_menu/tree_menu";
import { useTaxonomies } from "@/api/hooks/taxonomies/useTaxonomies";
import { useConceptSchemes } from "@/api/hooks/conceptSchemes/useConceptSchemes";
import { useOntologyClasses } from "@/api/hooks/ontologyClasses/useOntologyClasses";
import { buildHierarchicalTree } from "@/utils/treeBuilder";
import { ChartData } from "@/components/graphs/tree_chart/tree_data";
import { apiLogger } from "@/api/utils/logger";

export interface TreeMenuPanelProps {
  /**
   * Optional term ID to highlight in the tree
   */
  highlightedTermId?: string;

  /**
   * Optional callback when a node is clicked
   */
  onNodeClick?: (node: any) => void;

  /**
   * Additional CSS classes to apply to the panel container
   */
  className?: string;

  /**
   * Loading component to display while data is being fetched
   */
  loadingComponent?: React.ReactNode;

  /**
   * Error component to display when data loading fails
   */
  errorComponent?: React.ReactNode;

  /**
   * Optional view identifier for persisting expand state
   * If not provided, expand state will not be persisted to session storage
   */
  viewId?: string;
}

/**
 * TreeMenuPanel - A reusable navigation menu that displays the hierarchical
 * structure of layers, domains, and terms in a compressed format.
 *
 * Features:
 * - Automatically loads layers, domains, and terms data
 * - Builds hierarchical tree structure using treeBuilder utility
 * - Compact visualization suitable for sidebars
 * - Handles loading and error states
 * - Optional node click handling
 */
export function TreeMenuPanel({
  highlightedTermId,
  onNodeClick,
  className = "",
  loadingComponent,
  errorComponent,
  viewId,
}: TreeMenuPanelProps) {
  // Container ref to measure width
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);

  // Measure container width on mount and resize
  useEffect(() => {
    const measureWidth = () => {
      if (containerRef.current) {
        const width = containerRef.current.clientWidth;
        setContainerWidth(width);
      }
    };

    // Initial measurement
    measureWidth();

    // Add resize listener
    const resizeObserver = new ResizeObserver(measureWidth);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  // Load all base data
  const { data: taxonomies, isLoading: layersLoading } = useTaxonomies();
  const { data: conceptSchemes, isLoading: domainsLoading } =
    useConceptSchemes();
  const { data: ontologyClasses, isLoading: termsLoading } =
    useOntologyClasses();

  // Transform data to compatible format for treeBuilder
  const layers = taxonomies?.map((t) => ({
    ...t,
    node_type: "layer",
    parent_node_id: null,
    definition: t.description || "",
  }));

  const domains = conceptSchemes?.map((cs) => ({
    ...cs,
    node_type: "domain",
    parent_node_id: cs.taxonomy_id,
    definition: cs.description || "",
  }));

  const terms = ontologyClasses?.map((oc) => ({
    ...oc,
    node_type: "term",
    parent_node_id: oc.parent_class_id || oc.scheme_id,
  }));

  // Determine loading state
  const isLoading = layersLoading || domainsLoading || termsLoading;

  // Determine error state
  const error = null;

  // Build chart data
  const chartData = React.useMemo((): ChartData | null => {
    if (!layers || !domains || !terms) {
      return null;
    }

    try {
      // Build the complete tree
      const completeTree = buildHierarchicalTree({
        layers,
        domains,
        terms,
      });

      return {
        root: completeTree,
      } as ChartData;
    } catch (err) {
      apiLogger.error("Error building menu data", { error: err });
      return null;
    }
  }, [layers, domains, terms]);

  // Find path to highlighted node for auto-expansion
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const highlightedPath = React.useMemo(() => {
    if (!chartData || !highlightedTermId) {
      return [];
    }

    // Helper function to find path to a node
    const findPath = (
      node: any,

      targetId: string,
      path: string[] = [],
    ): string[] | null => {
      if (node.id === targetId) {
        return path;
      }

      if (node.children) {
        for (const child of node.children) {
          const childPath = findPath(child, targetId, [...path, node.id]);
          if (childPath) {
            return childPath;
          }
        }
      }

      return null;
    };

    const path = findPath(chartData.root, highlightedTermId);
    return path || [];
  }, [chartData, highlightedTermId]);

  // Handle loading state
  if (isLoading) {
    return (
      <div
        ref={containerRef}
        className={`flex items-center justify-center p-4 ${className}`}
      >
        {loadingComponent || <Spinner size="sm" />}
      </div>
    );
  }

  // Handle error state
  if (error) {
    apiLogger.error("TreeMenuPanel error", { error });

    if (errorComponent) {
      return (
        <div ref={containerRef} className={className}>
          {errorComponent}
        </div>
      );
    }

    return (
      <div
        ref={containerRef}
        className={`flex items-center justify-center p-4 text-red-600 ${className}`}
      >
        <div className="text-center text-sm">
          <p className="font-semibold">Error loading data</p>
        </div>
      </div>
    );
  }

  // Handle no data state
  if (!chartData) {
    return (
      <div
        ref={containerRef}
        className={`flex items-center justify-center p-4 text-gray-600 ${className}`}
      >
        <div className="text-center text-sm">
          <p>No data available</p>
        </div>
      </div>
    );
  }

  // Render the tree menu
  return (
    <div ref={containerRef} className={className}>
      <TreeMenu
        chartData={chartData}
        highlightedTermId={highlightedTermId}
        onNodeClick={onNodeClick}
        viewId={viewId}
        containerWidth={containerWidth}
        //initialExpandState={initialExpandState}
      />
    </div>
  );
}

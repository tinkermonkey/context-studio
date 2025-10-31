import React from "react";
import { Spinner } from "flowbite-react";
import { TreeMenu } from "@/components/graphs/tree_menu/tree_menu";
import {
  useLayerNodes,
  useDomainNodes,
  useTermNodes,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import {
  buildHierarchicalTree,
} from "@/utils/treeBuilder";
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
  // Load all base data
  const {
    data: layers,
    isLoading: layersLoading,
    error: layersError,
  } = useLayerNodes();
  const {
    data: domains,
    isLoading: domainsLoading,
    error: domainsError,
  } = useDomainNodes();
  const {
    data: terms,
    isLoading: termsLoading,
    error: termsError,
  } = useTermNodes();

  // Determine loading state
  const isLoading = layersLoading || domainsLoading || termsLoading;

  // Determine error state
  const error = layersError || domainsError || termsError;

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

  // Handle loading state
  if (isLoading) {
    return (
      <div className={`flex items-center justify-center p-4 ${className}`}>
        {loadingComponent || <Spinner size="sm" />}
      </div>
    );
  }

  // Handle error state
  if (error) {
    apiLogger.error("TreeMenuPanel error", { error });

    if (errorComponent) {
      return <div className={className}>{errorComponent}</div>;
    }

    return (
      <div
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
    <div className={className}>
      <TreeMenu
        chartData={chartData}
        highlightedTermId={highlightedTermId}
        onNodeClick={onNodeClick}
        viewId={viewId}
      />
    </div>
  );
}

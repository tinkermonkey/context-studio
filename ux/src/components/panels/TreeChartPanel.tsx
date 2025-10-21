import React from "react";
import { Spinner } from "flowbite-react";
import { TreeChart } from "@/components/graphs/hierarchy/tree_chart";
import {
  useLayerNodes,
  useDomainNodes,
  useTermNodes,
  useStructureNode,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import { useTermHierarchy } from "@/api/hooks/graph/useGraph";
import {
  buildHierarchicalTree,
  filterTreeByTerm,
  collectAllNodeIds,
} from "@/utils/treeBuilder";
import { ChartData } from "@/components/graphs/hierarchy/tree_data";
import { apiLogger } from "@/api/utils/logger";
import { NodeType } from "@/api/types/structureNodes";

export interface TreeChartPanelProps {
  /**
   * Optional term ID to filter the tree to show only direct parents and children
   * If not provided, shows the complete hierarchy
   */
  termId?: string;

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
}

/**
 * TreeChartPanel - A reusable component that encapsulates data loading and tree building
 * for hierarchical visualization of layers, domains, and terms.
 *
 * Features:
 * - Automatically loads layers, domains, and terms data
 * - Builds hierarchical tree structure using treeBuilder utility
 * - Optional filtering by term_id to show focused view
 * - Handles loading and error states
 */
export function TreeChartPanel({
  termId,
  className = "",
  loadingComponent,
  errorComponent,
}: TreeChartPanelProps) {
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

  // Load specific term if termId is provided
  const {
    data: targetTerm,
    isLoading: termLoading,
    error: termError,
  } = useStructureNode(termId || "");

  // Load term hierarchy to get all ancestors
  const {
    data: termHierarchy,
    isLoading: hierarchyLoading,
    error: hierarchyError,
  } = useTermHierarchy(termId || "");

  // Determine loading state
  const isLoading =
    layersLoading ||
    domainsLoading ||
    termsLoading ||
    (termId && (termLoading || hierarchyLoading));

  // Determine error state
  const error =
    layersError ||
    domainsError ||
    termsError ||
    (termId && (termError || hierarchyError));

  // Build chart data and collect initial expand state
  const { chartData, initialExpandState } = React.useMemo((): {
    chartData: ChartData | null;
    initialExpandState?: string[];
  } => {
    if (!layers || !domains || !terms) {
      return { chartData: null };
    }

    try {
      // Ensure targetTerm and all its ancestors are included in the appropriate arrays
      let allTerms = terms;
      let allDomains = domains;
      let allLayers = layers;

      if (termId && targetTerm) {
        // Add targetTerm if not present
        if (!terms.some((t) => t.id === termId)) {
          allTerms = [...terms, targetTerm];
        }

        // Process ancestors from hierarchy to ensure they're in the tree
        if (termHierarchy) {
          const ancestors = (termHierarchy.ancestors as Array<{
            id: string;
            type: string;
            title: string;
            definition?: string;
            parent_node_id?: string;
            distance: number;
          }>) || [];

          // Add missing ancestor terms
          const ancestorTerms = ancestors.filter((a) => a.type === "term");
          for (const ancestorTerm of ancestorTerms) {
            if (!allTerms.some((t) => t.id === ancestorTerm.id)) {
              allTerms = [
                ...allTerms,
                {
                  id: ancestorTerm.id,
                  title: ancestorTerm.title,
                  definition: ancestorTerm.definition || "",
                  node_type: NodeType.TERM,
                  parent_node_id: ancestorTerm.parent_node_id,
                  structural_predicate_id: undefined,
                  title_embedding: undefined,
                  definition_embedding: undefined,
                  created_at: "",
                  version: 1,
                  last_modified: "",
                },
              ];
            }
          }

          // Add missing ancestor domains
          const ancestorDomains = ancestors.filter((a) => a.type === "domain");
          for (const ancestorDomain of ancestorDomains) {
            if (!allDomains.some((d) => d.id === ancestorDomain.id)) {
              allDomains = [
                ...allDomains,
                {
                  id: ancestorDomain.id,
                  title: ancestorDomain.title,
                  definition: ancestorDomain.definition || "",
                  node_type: NodeType.DOMAIN,
                  parent_node_id: ancestorDomain.parent_node_id,
                  structural_predicate_id: undefined,
                  title_embedding: undefined,
                  definition_embedding: undefined,
                  created_at: "",
                  version: 1,
                  last_modified: "",
                },
              ];
            }
          }

          // Add missing ancestor layers
          const ancestorLayers = ancestors.filter((a) => a.type === "layer");
          for (const ancestorLayer of ancestorLayers) {
            if (!allLayers.some((l) => l.id === ancestorLayer.id)) {
              allLayers = [
                ...allLayers,
                {
                  id: ancestorLayer.id,
                  title: ancestorLayer.title,
                  definition: ancestorLayer.definition || "",
                  node_type: NodeType.LAYER,
                  parent_node_id: ancestorLayer.parent_node_id,
                  structural_predicate_id: undefined,
                  title_embedding: undefined,
                  definition_embedding: undefined,
                  created_at: "",
                  version: 1,
                  last_modified: "",
                },
              ];
            }
          }
        }
      }

      // Build the complete tree
      const completeTree = buildHierarchicalTree({
        layers: allLayers,
        domains: allDomains,
        terms: allTerms,
      });

      // If termId is provided, filter the tree and expand all nodes
      if (termId && targetTerm) {
        const filteredTree = filterTreeByTerm(completeTree, termId);

        // Collect all node IDs from the filtered tree for initial expansion
        const nodeIdsToExpand = collectAllNodeIds(filteredTree);

        return {
          chartData: {
            root: filteredTree,
          } as ChartData,
          initialExpandState: nodeIdsToExpand,
        };
      }

      // Return complete tree without initial expansion
      return {
        chartData: {
          root: completeTree,
        } as ChartData,
      };
    } catch (err) {
      apiLogger.error("Error building chart data", { error: err, termId });
      return { chartData: null };
    }
  }, [layers, domains, terms, termId, targetTerm, termHierarchy]);

  // Handle loading state
  if (isLoading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        {loadingComponent || <Spinner size="lg" />}
      </div>
    );
  }

  // Handle error state
  if (error) {
    apiLogger.error("TreeChartPanel error", { error, termId });

    if (errorComponent) {
      return <div className={className}>{errorComponent}</div>;
    }

    return (
      <div
        className={`flex items-center justify-center p-8 text-red-600 ${className}`}
      >
        <div className="text-center">
          <p className="text-lg font-semibold">Error loading data</p>
          <p className="mt-2 text-sm">
            {error instanceof Error
              ? error.message
              : "An unexpected error occurred"}
          </p>
        </div>
      </div>
    );
  }

  // Handle no data state
  if (!chartData) {
    return (
      <div
        className={`flex items-center justify-center p-8 text-gray-600 ${className}`}
      >
        <div className="text-center">
          <p className="text-lg">No data available</p>
          {termId && (
            <p className="mt-2 text-sm">
              Unable to load data for term: {termId}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Render the tree chart
  return (
    <div className={className}>
      <TreeChart
        chartData={chartData}
        initialExpandState={initialExpandState}
        highlightedTermId={termId}
      />
    </div>
  );
}

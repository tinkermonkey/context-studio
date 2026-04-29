import React from "react";
import { Spinner } from "flowbite-react";
import { TreeMenu } from "@/components/graphs/tree_menu/tree_menu";
import { useTaxonomies } from "@/api/hooks/taxonomies/useTaxonomies";
import { useConceptSchemes } from "@/api/hooks/conceptSchemes/useConceptSchemes";
import { useOntologyClasses } from "@/api/hooks/ontologyClasses/useOntologyClasses";
import { useOntologyClass } from "@/api/hooks/ontologyClasses/useOntologyClasses";
import { useTermHierarchy } from "@/api/hooks/graph/useGraph";
import {
  buildHierarchicalTree,
  filterTreeByTerm,
  collectAllNodeIds,
  collectNodeIdsUpToType,
} from "@/utils/treeBuilder";
import { ChartData } from "@/components/graphs/tree_chart/tree_data";
import { apiLogger } from "@/api/utils/logger";
import { NodeType } from "@/api/types/structureNodes";

export interface TreeChartPanelProps {
  /**
   * Optional term ID to filter the tree to show only direct parents and children
   * If not provided, shows the complete hierarchy
   */
  termId?: string;

  /**
   * Optional domain ID to filter the tree to show only direct parents and children
   * If not provided, shows the complete hierarchy
   */
  domainId?: string;

  /**
   * Optional layer ID to filter the tree to show only direct parents and children
   * If not provided, shows the complete hierarchy
   */
  layerId?: string;

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
 * TreeChartPanel - A reusable component that encapsulates data loading and tree building
 * for hierarchical visualization of layers, domains, and terms.
 *
 * Features:
 * - Automatically loads layers, domains, and terms data
 * - Builds hierarchical tree structure using treeBuilder utility
 * - Optional filtering by term_id, domain_id, or layer_id to show focused view
 * - Handles loading and error states
 */
export function TreeChartPanel({
  termId,
  domainId,
  layerId,
  className = "",
  loadingComponent,
  errorComponent,
  viewId,
}: TreeChartPanelProps) {
  // Load all base data
  const {
    data: taxonomies,
    isLoading: layersLoading,
    error: layersError,
  } = useTaxonomies();
  const {
    data: conceptSchemes,
    isLoading: domainsLoading,
    error: domainsError,
  } = useConceptSchemes();
  const {
    data: ontologyClasses,
    isLoading: termsLoading,
    error: termsError,
  } = useOntologyClasses();

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

  // Load specific term if termId is provided
  const {
    data: targetTerm,
    isLoading: termLoading,
    error: termError,
  } = useOntologyClass(termId || "");

  // Load term hierarchy to get all ancestors
  const {
    data: termHierarchy,
    isLoading: hierarchyLoading,
    error: hierarchyError,
  } = useTermHierarchy(termId || "");

  // Load specific domain if domainId is provided - need to find from conceptSchemes
  const targetDomain =
    domainId && domains ? domains.find((d) => d.id === domainId) : null;
  const domainLoading = domainsLoading;
  const domainError = domainsError;

  // Load specific layer if layerId is provided - need to find from taxonomies
  const targetLayer =
    layerId && layers ? layers.find((l) => l.id === layerId) : null;
  const layerLoading = layersLoading;
  const layerError = layersError;

  // Determine loading state
  const isLoading =
    layersLoading ||
    domainsLoading ||
    termsLoading ||
    (termId && (termLoading || hierarchyLoading)) ||
    (domainId && domainLoading) ||
    (layerId && layerLoading);

  // Determine error state
  const error =
    layersError ||
    domainsError ||
    termsError ||
    (termId && (termError || hierarchyError)) ||
    (domainId && domainError) ||
    (layerId && layerError);

  // Build chart data and collect initial expand state
  const { chartData, initialExpandState } = React.useMemo((): {
    chartData: ChartData | null;
    initialExpandState?: string[];
  } => {
    if (!layers || !domains || !terms) {
      return { chartData: null };
    }

    try {
      // Determine which node we're filtering by
      const filterNodeId = termId || domainId || layerId;
      const targetNode = termId
        ? targetTerm
        : domainId
          ? targetDomain
          : layerId
            ? targetLayer
            : null;

      // Ensure target node and all its ancestors are included in the appropriate arrays
      let allTerms = terms;
      let allDomains = domains;
      let allLayers = layers;

      if (termId && targetTerm) {
        // Add targetTerm if not present - transform to include required properties
        if (!terms.some((t) => t.id === termId)) {
          const transformedTerm = {
            ...targetTerm,
            node_type: "term",
            parent_node_id: targetTerm.parent_class_id || targetTerm.scheme_id,
          };
          allTerms = [...terms, transformedTerm];
        }

        // Process ancestors from hierarchy to ensure they're in the tree
        if (termHierarchy) {
          const ancestors =
            (termHierarchy.ancestors as Array<{
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
                  ...targetTerm,
                  id: ancestorTerm.id,
                  title: ancestorTerm.title,
                  definition: ancestorTerm.definition || "",
                  node_type: NodeType.TERM,
                  parent_node_id: ancestorTerm.parent_node_id || targetTerm.scheme_id,
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
                  ...domains[0],
                  id: ancestorDomain.id,
                  title: ancestorDomain.title,
                  definition: ancestorDomain.definition || "",
                  node_type: NodeType.DOMAIN,
                  parent_node_id: ancestorDomain.parent_node_id || "",
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
                  ...layers[0],
                  id: ancestorLayer.id,
                  title: ancestorLayer.title,
                  definition: ancestorLayer.definition || "",
                  node_type: NodeType.LAYER,
                  parent_node_id: null,
                },
              ];
            }
          }
        }
      }

      if (domainId && targetDomain) {
        // Add targetDomain if not present
        if (!allDomains.some((d) => d.id === domainId)) {
          allDomains = [...allDomains, targetDomain];
        }

        // For domains, we don't have a hierarchy endpoint by domain_id
        // We rely on the data already loaded including parent relationships
        // If needed, we could walk up parent_node_id chain here
      }

      if (layerId && targetLayer) {
        // Add targetLayer if not present
        if (!allLayers.some((l) => l.id === layerId)) {
          allLayers = [...allLayers, targetLayer];
        }

        // For layers, we don't have a hierarchy endpoint by layer_id
        // We rely on the data already loaded including parent relationships
        // If needed, we could walk up parent_node_id chain here
      }

      // Build the complete tree
      const completeTree = buildHierarchicalTree({
        layers: allLayers,
        domains: allDomains,
        terms: allTerms,
      });

      // If termId, domainId, or layerId is provided, filter the tree and expand nodes
      if (filterNodeId && targetNode) {
        const filteredTree = filterTreeByTerm(completeTree, filterNodeId);

        // Determine expansion strategy based on node type
        let nodeIdsToExpand: string[];

        if (layerId) {
          // For layers, only expand the dataset root and layer itself (domains stay collapsed)
          // This shows the domains but keeps them collapsed
          nodeIdsToExpand = ["dataset", layerId];
        } else if (domainId) {
          // For domains, expand all nodes up to and including domains (terms stay collapsed)
          // This expands the parent layer(s) and domain to show the full path, but keeps terms collapsed
          nodeIdsToExpand = collectNodeIdsUpToType(filteredTree, "domain");
        } else {
          // For terms, expand all nodes
          nodeIdsToExpand = collectAllNodeIds(filteredTree);
        }

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
      apiLogger.error("Error building chart data", {
        error: err,
        termId,
        domainId,
        layerId,
      });
      return { chartData: null };
    }
  }, [
    layers,
    domains,
    terms,
    termId,
    targetTerm,
    termHierarchy,
    domainId,
    targetDomain,
    layerId,
    targetLayer,
  ]);

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
          {domainId && (
            <p className="mt-2 text-sm">
              Unable to load data for domain: {domainId}
            </p>
          )}
          {layerId && (
            <p className="mt-2 text-sm">
              Unable to load data for layer: {layerId}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Render the tree menu with definitions
  return (
    <div className={className}>
      <TreeMenu
        chartData={chartData}
        initialExpandState={initialExpandState}
        highlightedTermId={termId || domainId || layerId}
        viewId={viewId}
        showDefinitions={true}
        titleWidth={0.2}
      />
    </div>
  );
}

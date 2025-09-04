import React from "react";
import { Spinner } from "flowbite-react";
import { TreeChart } from "@/components/graphs/hierarchy/tree_chart";
import { useLayers } from "@/api/hooks/layers/useLayers";
import { useDomains } from "@/api/hooks/domains/useDomains";
import { useTerms, useTerm } from "@/api/hooks/terms/useTerms";
import { buildHierarchicalTree, filterTreeByTerm, collectAllNodeIds } from "@/utils/treeBuilder";
import { ChartData } from "@/components/graphs/hierarchy/tree_data";
import { apiLogger } from "@/api/utils/logger";

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
  errorComponent
}: TreeChartPanelProps) {
  // Load all base data
  const { data: layers, isLoading: layersLoading, error: layersError } = useLayers();
  const { data: domains, isLoading: domainsLoading, error: domainsError } = useDomains();
  const { data: terms, isLoading: termsLoading, error: termsError } = useTerms();
  
  // Load specific term if termId is provided
  const { data: targetTerm, isLoading: termLoading, error: termError } = useTerm(
    termId || "", 
    !!termId
  );

  // Determine loading state
  const isLoading = layersLoading || domainsLoading || termsLoading || (termId && termLoading);
  
  // Determine error state
  const error = layersError || domainsError || termsError || (termId && termError);

  // Build chart data and collect initial expand state
  const { chartData, initialExpandState } = React.useMemo((): { 
    chartData: ChartData | null;
    initialExpandState?: string[];
  } => {
    if (!layers || !domains || !terms) {
      return { chartData: null };
    }

    try {
      // Build the complete tree first
      const completeTree = buildHierarchicalTree({ layers, domains, terms });
      
      // If termId is provided, filter the tree and expand all nodes
      if (termId && targetTerm) {
        apiLogger.info('Filtering tree by term', { termId, targetTerm });
        const filteredTree = filterTreeByTerm(completeTree, termId);
        
        // Collect all node IDs from the filtered tree for initial expansion
        const nodeIdsToExpand = collectAllNodeIds(filteredTree);
        
        return {
          chartData: {
            root: filteredTree,
          } as ChartData,
          initialExpandState: nodeIdsToExpand
        };
      }
      
      // Return complete tree without initial expansion
      return {
        chartData: {
          root: completeTree,
        } as ChartData
      };
      
    } catch (err) {
      apiLogger.error('Error building chart data', { error: err, termId });
      return { chartData: null };
    }
  }, [layers, domains, terms, termId, targetTerm]);

  // Handle loading state
  if (isLoading) {
    return (
      <div className={`flex justify-center items-center p-8 ${className}`}>
        {loadingComponent || <Spinner size="lg" />}
      </div>
    );
  }

  // Handle error state
  if (error) {
    apiLogger.error('TreeChartPanel error', { error, termId });
    
    if (errorComponent) {
      return <div className={className}>{errorComponent}</div>;
    }
    
    return (
      <div className={`flex justify-center items-center p-8 text-red-600 ${className}`}>
        <div className="text-center">
          <p className="text-lg font-semibold">Error loading data</p>
          <p className="text-sm mt-2">
            {error instanceof Error ? error.message : 'An unexpected error occurred'}
          </p>
        </div>
      </div>
    );
  }

  // Handle no data state
  if (!chartData) {
    return (
      <div className={`flex justify-center items-center p-8 text-gray-600 ${className}`}>
        <div className="text-center">
          <p className="text-lg">No data available</p>
          {termId && (
            <p className="text-sm mt-2">
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

import { apiLogger } from '@/api/utils/logger';
import { HierarchyNode } from '@/components/graphs/hierarchy/tree_data';

export interface TreeBuilderInput {
  layers: any[];
  domains: any[];
  terms: any[];
}

/**
 * Transforms API data (layers, domains, terms) into a hierarchical tree structure
 * suitable for visualization components.
 * 
 * @param input - Object containing layers, domains, and terms arrays from API
 * @returns HierarchyNode representing the complete hierarchy
 */
export function buildHierarchicalTree(input: TreeBuilderInput): HierarchyNode {
  const { layers, domains, terms } = input;

  if (!layers || !domains || !terms) {
    return {
      id: 'dataset',
      title: 'No Data Set',
      type: 'dataset',
      depth: 0,
      children: [],
    };
  }

  try {
    // Debug: log layers and domains
    //console.log('LAYERS:', layers);
    //console.log('DOMAINS:', domains);

    const rootNode: HierarchyNode = {
      id: 'dataset',
      title: 'Data Set',
      type: 'dataset',
      children: [],
      depth: 0
    };

    // Group domains by layer_id for efficient lookup
    const domainsByLayer = new Map<string, any[]>();
    domains.forEach((domain: any) => {
      if (domain.layer_id == null) {
        console.warn('Domain missing layer_id:', domain);
        return;
      }
      const layerId = String(domain.layer_id);
      if (!domainsByLayer.has(layerId)) {
        domainsByLayer.set(layerId, []);
      }
      domainsByLayer.get(layerId)!.push(domain);
    });

    // Build layer nodes with their domains
    rootNode.children = layers
      .filter((layer: any) => layer.id != null)
      .map((layer: any) => {
        const layerIdStr = String(layer.id);
        const layerDomains = domainsByLayer.get(layerIdStr) || [];
        
        if (layerDomains.length === 0) {
          console.debug('Layer has no domains:', layer, 'Available keys:', Array.from(domainsByLayer.keys()));
        }
        
        const layerNode: HierarchyNode = {
          id: `${layer.id}`,
          title: layer.title || layer.name || `Layer ${layer.id}`,
          definition: layer.definition || '',
          type: 'layer',
          children: [],
          depth: rootNode.depth + 1,
        };

        // Build domain nodes with their terms
        layerNode.children = layerDomains
          .filter((domain: any) => domain.id != null)
          .map((domain: any) => {
            const domainTerms = terms.filter((term: any) => String(term.domain_id) === String(domain.id));

            const domainNode: HierarchyNode = {
              id: `${domain.id}`,
              title: domain.title || domain.name || `Domain ${domain.id}`,
              definition: domain.definition || '',
              type: 'domain',
              children: [],
              depth: layerNode.depth + 1,
            };

            // Build hierarchical term structure
            const { topLevelTerms } = buildTermHierarchy(domainTerms);
            domainNode.children = topLevelTerms;
            
            return domainNode;
          });
          
        return layerNode;
      });

    console.log('Final tree structure:', rootNode);
    return rootNode;
    
  } catch (err) {
    apiLogger.error('Error transforming data to tree:', { error: err });
    throw new Error('Failed to transform data to tree structure');
  }
}

/**
 * Builds a hierarchical structure from a flat array of terms
 * by organizing them based on parent_term_id relationships.
 * 
 * @param terms - Array of term objects with potential parent_term_id relationships
 * @returns Object containing the top-level terms and a map of all terms
 */
function buildTermHierarchy(terms: any[]): { 
  topLevelTerms: HierarchyNode[]; 
  termMap: Map<string, HierarchyNode>; 
} {
  const termMap = new Map<string, HierarchyNode>();
  const topLevelTerms: HierarchyNode[] = [];

  // First pass: create all term nodes
  terms.forEach((term: any) => {
    if (!term.id) {
      console.warn('Term missing id:', term);
      return;
    }
    termMap.set(term.id, {
      id: `${term.id}`,
      title: term.title || term.name || `Term ${term.id}`,
      definition: term.definition || '',
      type: 'term',
      children: [],
      depth: 0,
    });
  });

  // Second pass: establish parent-child relationships
  terms.forEach((term: any) => {
    const termNode = termMap.get(term.id);
    if (!termNode) return;

    if (term.parent_term_id && termMap.has(term.parent_term_id)) {
      // This term has a parent - add it to parent's children
      const parentNode = termMap.get(term.parent_term_id)!;
      if (parentNode.children) {
        parentNode.children.push(termNode);
      }
    } else {
      // This is a top-level term
      topLevelTerms.push(termNode);
    }
  });

  return { topLevelTerms, termMap };
}

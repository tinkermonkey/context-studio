/**
 * Types for Streaming Reference Search
 * Extends unified types to support real-time streaming from multiple sources
 */

import {
  SourceType,
  UnifiedSearchRequest,
  UnifiedSearchResponse,
  UnifiedNode,
  SearchLink,
  SOURCE_METADATA,
} from "./unified";

/**
 * Status of an individual source during streaming search
 */
export type SourceSearchStatus = "pending" | "loading" | "completed" | "error";

/**
 * Individual source response as it arrives
 */
export interface SourceSearchUpdate {
  source: SourceType;
  status: SourceSearchStatus;
  results?: UnifiedNode[];
  links?: SearchLink[];
  error?: string;
  execution_time_ms?: number;
  total_results?: number;
}

/**
 * Deduplication statistics for tracking
 */
export interface DeduplicationStats {
  originalNodes: number;
  deduplicatedNodes: number;
  originalLinks: number;
  deduplicatedLinks: number;
  crossReferences: number;
  duplicatesRemoved: number;
}

/**
 * Complete streaming search state
 */
export interface StreamingSearchState {
  query: string;
  request: UnifiedSearchRequest;
  sources: Record<SourceType, SourceSearchUpdate>;
  aggregatedResults: UnifiedNode[];
  aggregatedLinks: SearchLink[];
  totalResults: number;
  isComplete: boolean;
  hasAnyResults: boolean;
  completedSources: SourceType[];
  errorSources: SourceType[];
  startTime: number;
  endTime?: number;
  deduplicationStats?: DeduplicationStats;
}

/**
 * Callback function for streaming updates
 */
export type StreamingUpdateCallback = (update: SourceSearchUpdate) => void;

/**
 * Callback function for complete state updates
 */
export type StreamingStateCallback = (state: StreamingSearchState) => void;

/**
 * Options for streaming search
 */
export interface StreamingSearchOptions {
  onSourceUpdate?: StreamingUpdateCallback;
  onStateChange?: StreamingStateCallback;
  timeout?: number; // Per-source timeout in ms
  retryAttempts?: number;
  includePartialResults?: boolean;
}

/**
 * Result of starting a streaming search
 */
export interface StreamingSearchControl {
  cancel: () => void;
  getState: () => StreamingSearchState;
  isActive: boolean;
}

/**
 * Configuration for available sources and their endpoints
 */
export interface SourceEndpointConfig {
  endpoint: string;
  enabled: boolean;
  timeout?: number;
  priority?: number; // Lower number = higher priority
}

/**
 * Mapping of sources to their individual endpoints
 */
export const SOURCE_ENDPOINTS: Record<SourceType, SourceEndpointConfig> = {
  dbpedia: {
    endpoint: "/api/reference/dbpedia/search",
    enabled: true,
    timeout: 30000,
    priority: 1,
  },
  schema_org: {
    endpoint: "/api/reference/schema-org/search",
    enabled: true,
    timeout: 30000,
    priority: 2,
  },
  conceptnet: {
    endpoint: "/api/reference/conceptnet/search",
    enabled: true,
    timeout: 30000,
    priority: 3,
  },
  wikidata: {
    endpoint: "/api/reference/wikidata/search",
    enabled: true,
    timeout: 30000,
    priority: 4,
  },
};

/**
 * Get enabled sources in priority order
 */
export function getEnabledSources(): SourceType[] {
  return Object.entries(SOURCE_ENDPOINTS)
    .filter(([, config]) => config.enabled)
    .sort((a, b) => (a[1].priority || 999) - (b[1].priority || 999))
    .map(([source]) => source as SourceType);
}

/**
 * Create initial streaming state
 */
export function createInitialStreamingState(
  request: UnifiedSearchRequest
): StreamingSearchState {
  const enabledSources = getEnabledSources();
  const sources: Record<SourceType, SourceSearchUpdate> = {} as Record<SourceType, SourceSearchUpdate>;

  // Initialize all enabled sources with pending status
  enabledSources.forEach(source => {
    sources[source] = {
      source,
      status: "pending",
      results: [],
      links: [],
    };
  });

  return {
    query: request.query,
    request,
    sources,
    aggregatedResults: [],
    aggregatedLinks: [],
    totalResults: 0,
    isComplete: false,
    hasAnyResults: false,
    completedSources: [],
    errorSources: [],
    startTime: Date.now(),
  };
}

/**
 * Deduplicate nodes by ID, keeping first occurrence
 */
function deduplicateNodes(nodes: UnifiedNode[]): UnifiedNode[] {
  const seenIds = new Set<string>();
  return nodes.filter(node => {
    if (seenIds.has(node.id)) {
      return false;
    }
    seenIds.add(node.id);
    return true;
  });
}

/**
 * Deduplicate links by ID and filter to only include links between existing nodes
 */
function deduplicateLinks(links: SearchLink[], nodeIds: Set<string>): SearchLink[] {
  const seenIds = new Set<string>();
  return links.filter(link => {
    // Skip if we've already seen this link ID
    if (seenIds.has(link.id)) {
      return false;
    }

    // Only include links where both subject and object nodes exist in our results
    if (!nodeIds.has(link.subject) || !nodeIds.has(link.object)) {
      return false;
    }

    seenIds.add(link.id);
    return true;
  });
}

/**
 * Simple cross-reference discovery based on title similarity and common properties
 * Replicates the server-side _discover_cross_references logic
 */
function discoverCrossReferences(nodes: UnifiedNode[]): SearchLink[] {
  const crossLinks: SearchLink[] = [];
  const nodesByTitle = new Map<string, UnifiedNode[]>();

  // Group nodes by normalized title for cross-reference detection
  nodes.forEach(node => {
    const normalizedTitle = node.title.toLowerCase().trim();
    if (!nodesByTitle.has(normalizedTitle)) {
      nodesByTitle.set(normalizedTitle, []);
    }
    nodesByTitle.get(normalizedTitle)!.push(node);
  });

  // Create cross-reference links between nodes with same title from different sources
  nodesByTitle.forEach((nodesGroup, title) => {
    if (nodesGroup.length > 1) {
      // Create links between nodes from different sources
      for (let i = 0; i < nodesGroup.length; i++) {
        for (let j = i + 1; j < nodesGroup.length; j++) {
          const node1 = nodesGroup[i];
          const node2 = nodesGroup[j];

          // Only create cross-references between different sources
          if (node1.source !== node2.source) {
            const crossLinkId = `cross-ref-${node1.id}-${node2.id}`;
            crossLinks.push({
              id: crossLinkId,
              source: "cross-reference" as SourceType,
              subject: node1.id,
              predicate: "sameAs",
              object: node2.id,
              weight: 0.8, // High confidence for title matches
              attributes: {
                type: "cross-reference",
                reason: "title_match",
                confidence: 0.8
              }
            });
          }
        }
      }
    }
  });

  return crossLinks;
}

/**
 * Update streaming state with a source update
 * Includes deduplication and normalization logic from server-side implementation
 */
export function updateStreamingState(
  state: StreamingSearchState,
  update: SourceSearchUpdate
): StreamingSearchState {
  const newSources = {
    ...state.sources,
    [update.source]: update,
  };

  // Aggregate results from all completed sources
  const allResults: UnifiedNode[] = [];
  const allLinks: SearchLink[] = [];
  const completedSources: SourceType[] = [];
  const errorSources: SourceType[] = [];

  Object.values(newSources).forEach(sourceUpdate => {
    if (sourceUpdate.status === "completed" && sourceUpdate.results) {
      allResults.push(...sourceUpdate.results);
      completedSources.push(sourceUpdate.source);
      if (sourceUpdate.links) {
        allLinks.push(...sourceUpdate.links);
      }
    } else if (sourceUpdate.status === "error") {
      errorSources.push(sourceUpdate.source);
    }
  });

  // Apply deduplication and normalization (matching server-side logic)
  const deduplicatedNodes = deduplicateNodes(allResults);
  const nodeIds = new Set(deduplicatedNodes.map(node => node.id));
  const deduplicatedLinks = deduplicateLinks(allLinks, nodeIds);

  // Discover cross-references between sources (only if we have multiple sources)
  let crossReferences: SearchLink[] = [];
  const sourcesWithResults = new Set(
    deduplicatedNodes.map(node => node.source)
  );

  if (sourcesWithResults.size > 1) {
    crossReferences = discoverCrossReferences(deduplicatedNodes);
    // Filter cross-references to ensure both nodes exist and deduplicate
    crossReferences = deduplicateLinks(crossReferences, nodeIds);
  }

  // Combine original links with cross-references
  const finalLinks = [...deduplicatedLinks, ...crossReferences];

  // Calculate deduplication statistics (matching server-side logging)
  const deduplicationStats: DeduplicationStats = {
    originalNodes: allResults.length,
    deduplicatedNodes: deduplicatedNodes.length,
    originalLinks: allLinks.length,
    deduplicatedLinks: deduplicatedLinks.length,
    crossReferences: crossReferences.length,
    duplicatesRemoved: allResults.length - deduplicatedNodes.length,
  };

  // Log deduplication stats if there were duplicates (matching server behavior)
  if (deduplicationStats.duplicatesRemoved > 0 || crossReferences.length > 0) {
    console.log('Streaming search deduplication:', {
      query: state.query,
      originalNodes: deduplicationStats.originalNodes,
      deduplicatedNodes: deduplicationStats.deduplicatedNodes,
      duplicatesRemoved: deduplicationStats.duplicatesRemoved,
      originalLinks: deduplicationStats.originalLinks,
      finalLinks: finalLinks.length,
      crossReferences: crossReferences.length,
      sourcesWithResults: Array.from(sourcesWithResults),
    });
  }

  // Check if all enabled sources have completed (success or error)
  const enabledSources = getEnabledSources();
  const finishedSources = completedSources.length + errorSources.length;
  const isComplete = finishedSources >= enabledSources.length;

  return {
    ...state,
    sources: newSources,
    aggregatedResults: deduplicatedNodes,
    aggregatedLinks: finalLinks,
    totalResults: deduplicatedNodes.length,
    hasAnyResults: deduplicatedNodes.length > 0,
    completedSources,
    errorSources,
    isComplete,
    endTime: isComplete ? Date.now() : undefined,
    deduplicationStats,
  };
}

/**
 * Error types specific to streaming
 */
export class StreamingSearchError extends Error {
  constructor(
    message: string,
    public source?: SourceType,
    public originalError?: Error
  ) {
    super(message);
    this.name = "StreamingSearchError";
  }
}

export class StreamingTimeoutError extends StreamingSearchError {
  constructor(source: SourceType, timeoutMs: number) {
    super(`Search for ${source} timed out after ${timeoutMs}ms`, source);
    this.name = "StreamingTimeoutError";
  }
}
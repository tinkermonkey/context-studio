/**
 * LinkExplorer Component
 *
 * Explores and displays relationships between reference nodes
 */

import React, { useState, useMemo } from "react";
import { Alert, Badge, Button, Card, Select, Spinner } from "flowbite-react";;
import { ArrowLeft, ArrowRight, ExternalLink, Filter, Info, RotateCcw  } from "lucide-react";;
import {
  UnifiedLink,
  UnifiedNode,
  UnifiedSearchLink,
} from "@/api/types/unified";
import { SOURCE_METADATA } from "@/api/types/unified";
import { useNodeDetails } from "@/api/hooks/unifiedReference/useUnifiedReference";
import { getSourceBadgeColor, getSourceLabel } from "@/utils/sourceUtils";

// Adapter function to convert SearchLink to UnifiedLink format
const convertSearchLinkToUnifiedLink = (
  searchLink: UnifiedSearchLink,
): UnifiedLink => ({
  id: searchLink.id,
  source_node_id: searchLink.subject,
  target_node_id: searchLink.object,
  predicate: searchLink.predicate,
  source: searchLink.source,
  confidence_score: searchLink.weight || 1.0,
  metadata: searchLink.attributes || {},
});

interface LinkExplorerProps {
  nodeId: string;
  links: UnifiedLink[] | UnifiedSearchLink[];
  searchResults?: UnifiedNode[]; // Add search results to resolve linked nodes
  isLoading?: boolean;
  error?: Error | null;
  onNodeSelect?: (node: UnifiedNode) => void;
  showDirection?: boolean;
}

interface LinkItemProps {
  link: UnifiedLink;
  currentNodeId: string;
  searchResults?: UnifiedNode[]; // Add search results to resolve linked nodes
  onNodeSelect?: (node: UnifiedNode) => void;
}

const LinkItem: React.FC<LinkItemProps> = ({
  link,
  currentNodeId,
  searchResults = [],
  onNodeSelect,
}) => {
  const isOutgoing = link.source_node_id === currentNodeId;
  const targetNodeId = isOutgoing ? link.target_node_id : link.source_node_id;

  // Try to find the target node in search results first, fallback to API call
  const targetNodeFromSearch = searchResults.find(
    (node) => node.id === targetNodeId,
  );

  const {
    data: targetNodeFromAPI,
    isLoading: apiLoading,
  } = useNodeDetails(
    targetNodeFromSearch ? null : targetNodeId, // Only call API if not found in search results
  );

  const targetNode = targetNodeFromSearch || targetNodeFromAPI;
  const isLoading = !targetNodeFromSearch && apiLoading;

  const confidencePercent = Math.round(link.confidence_score * 100);

  const handleNodeClick = () => {
    if (targetNode && onNodeSelect) {
      onNodeSelect(targetNode);
    }
  };

  if (isLoading) {
    return (
      <Card className="animate-pulse">
        <div className="flex items-center space-x-4">
          <div className="h-4 w-1/4 rounded bg-gray-200"></div>
          <div className="h-4 w-1/2 rounded bg-gray-200"></div>
        </div>
      </Card>
    );
  }

  if (error || !targetNode) {
    return (
      <Card>
        <div className="flex items-center gap-2 text-gray-500">
          <Info className="h-4 w-4" />
          <span>Node details unavailable</span>
          <code className="rounded bg-gray-100 px-1 text-xs">
            {targetNodeId}
          </code>
        </div>
      </Card>
    );
  }

  return (
    <Card className="transition-shadow hover:shadow-md">
      <div className="space-y-3">
        {/* Link relationship */}
        <div className="flex items-center gap-2 text-sm">
          <Badge color={getSourceBadgeColor(link.source)} size="sm">
            {getSourceLabel(link.source)}
          </Badge>

          <div className="flex items-center gap-1 text-gray-600">
            {isOutgoing ? (
              <>
                <ArrowRight className="h-3 w-3" />
                <span className="font-medium">{link.predicate}</span>
              </>
            ) : (
              <>
                <ArrowLeft className="h-3 w-3" />
                <span className="font-medium">{link.predicate}⁻¹</span>
              </>
            )}
          </div>

          {link.confidence_score < 1 && (
            <Badge color="gray" size="sm">
              {confidencePercent}%
            </Badge>
          )}
        </div>

        {/* Target node info */}
        <div className="space-y-2">
          <h4 className="cursor-pointer font-semibold text-blue-600 transition-colors hover:text-blue-800">
            <button onClick={handleNodeClick} className="text-left">
              {targetNode.title}
            </button>
          </h4>

          {targetNode.definition && (
            <p className="line-clamp-2 text-sm text-gray-600">
              {targetNode.definition}
            </p>
          )}

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge color={getSourceBadgeColor(targetNode.source)} size="sm">
                {getSourceLabel(targetNode.source)}
              </Badge>
            </div>

            <div className="flex gap-1">
              <Button size="xs" color="blue" onClick={handleNodeClick}>
                View Details
              </Button>

              {targetNode.source_url && (
                <Button
                  size="xs"
                  color="gray"
                  onClick={() =>
                    targetNode.source_url &&
                    window.open(targetNode.source_url, "_blank")
                  }
                >
                  <ExternalLink className="h-3 w-3" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export const LinkExplorer: React.FC<LinkExplorerProps> = ({
  nodeId,
  links: rawLinks,
  searchResults = [],
  isLoading = false,
  error = null,
  onNodeSelect,
  showDirection = true,
}) => {
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [directionFilter, setDirectionFilter] = useState<
    "all" | "outgoing" | "incoming"
  >("all");
  const [predicateFilter, setPredicateFilter] = useState<string>("all");

  // Convert SearchLinks to UnifiedLinks if needed
  const links: UnifiedLink[] = useMemo(() => {
    return rawLinks.map((link) => {
      // Check if it's a SearchLink (has 'subject' property)
      if ("subject" in link) {
        return convertSearchLinkToUnifiedLink(link as UnifiedSearchLink);
      }
      // It's already a UnifiedLink
      return link as UnifiedLink;
    });
  }, [rawLinks]);

  // Get unique values for filters
  const { sources, predicates, outgoingLinks, incomingLinks } = useMemo(() => {
    const sources = [...new Set(links.map((link) => link.source))];
    const predicates = [...new Set(links.map((link) => link.predicate))];
    const outgoing = links.filter((link) => link.source_node_id === nodeId);
    const incoming = links.filter((link) => link.target_node_id === nodeId);

    return {
      sources,
      predicates,
      outgoingLinks: outgoing,
      incomingLinks: incoming,
    };
  }, [links, nodeId]);

  // Filter links based on current filters
  const filteredLinks = useMemo(() => {
    return links.filter((link) => {
      // Source filter
      if (sourceFilter !== "all" && link.source !== sourceFilter) {
        return false;
      }

      // Direction filter
      if (directionFilter === "outgoing" && link.source_node_id !== nodeId) {
        return false;
      }
      if (directionFilter === "incoming" && link.target_node_id !== nodeId) {
        return false;
      }

      // Predicate filter
      if (predicateFilter !== "all" && link.predicate !== predicateFilter) {
        return false;
      }

      return true;
    });
  }, [links, sourceFilter, directionFilter, predicateFilter, nodeId]);

  const clearFilters = () => {
    setSourceFilter("all");
    setDirectionFilter("all");
    setPredicateFilter("all");
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert color="failure" icon={Info}>
        Failed to load links: {error.message}
      </Alert>
    );
  }

  if (links.length === 0) {
    return (
      <Alert color="info" icon={Info}>
        <div className="space-y-2">
          <p className="font-medium">No relationships found</p>
          <p className="text-sm">
            This node doesn't have any recorded relationships with other nodes.
          </p>
        </div>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="flex items-center gap-2 font-semibold">
              <Filter className="h-4 w-4" />
              Filters
            </h4>

            <Button
              size="xs"
              color="gray"
              onClick={clearFilters}
              disabled={
                sourceFilter === "all" &&
                directionFilter === "all" &&
                predicateFilter === "all"
              }
            >
              <RotateCcw className="mr-1 h-3 w-3" />
              Clear
            </Button>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {/* Direction filter */}
            {showDirection && (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Direction
                </label>
                <Select
                  value={directionFilter}
                  onChange={(e) =>
                    setDirectionFilter(
                      e.target.value as "all" | "outgoing" | "incoming",
                    )
                  }
                  sizing="sm"
                >
                  <option value="all">All ({links.length})</option>
                  <option value="outgoing">
                    Outgoing ({outgoingLinks.length})
                  </option>
                  <option value="incoming">
                    Incoming ({incomingLinks.length})
                  </option>
                </Select>
              </div>
            )}

            {/* Source filter */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Source
              </label>
              <Select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                sizing="sm"
              >
                <option value="all">All Sources</option>
                {sources.map((source) => (
                  <option key={source} value={source}>
                    {SOURCE_METADATA[source]?.label || source}
                  </option>
                ))}
              </Select>
            </div>

            {/* Predicate filter */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Relationship
              </label>
              <Select
                value={predicateFilter}
                onChange={(e) => setPredicateFilter(e.target.value)}
                sizing="sm"
              >
                <option value="all">All Relationships</option>
                {predicates.map((predicate) => (
                  <option key={predicate} value={predicate}>
                    {predicate}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </div>
      </Card>

      {/* Results summary */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          Showing {filteredLinks.length} of {links.length} relationships
        </span>

        {showDirection && (
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <ArrowRight className="h-3 w-3" />
              {outgoingLinks.length} outgoing
            </span>
            <span className="flex items-center gap-1">
              <ArrowLeft className="h-3 w-3" />
              {incomingLinks.length} incoming
            </span>
          </div>
        )}
      </div>

      {/* Links list */}
      {filteredLinks.length === 0 ? (
        <Alert color="info" icon={Info}>
          No relationships match the current filters.
        </Alert>
      ) : (
        <div className="space-y-3">
          {filteredLinks.map((link) => (
            <LinkItem
              key={link.id}
              link={link}
              currentNodeId={nodeId}
              searchResults={searchResults}
              onNodeSelect={onNodeSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default LinkExplorer;

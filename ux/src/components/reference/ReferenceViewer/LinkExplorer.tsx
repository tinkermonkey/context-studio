/**
 * LinkExplorer Component
 *
 * Explores and displays relationships between reference nodes
 */

import React, { useState, useMemo } from 'react';
import { Card, Badge, Button, Alert, Spinner, Select } from 'flowbite-react';
import {
  ArrowRight,
  ArrowLeft,
  ArrowRightLeft,
  ExternalLink,
  Filter,
  RotateCcw,
  Info,
} from 'lucide-react';
import { UnifiedLink, UnifiedNode } from '@/api/types/unified';
import { SOURCE_METADATA } from '@/api/types/unified';
import { useNodeDetails } from '@/api/hooks/unifiedReference/useUnifiedReference';

interface LinkExplorerProps {
  nodeId: string;
  links: UnifiedLink[];
  isLoading?: boolean;
  error?: Error | null;
  onNodeSelect?: (node: UnifiedNode) => void;
  showDirection?: boolean;
}

interface LinkItemProps {
  link: UnifiedLink;
  currentNodeId: string;
  onNodeSelect?: (node: UnifiedNode) => void;
}

const LinkItem: React.FC<LinkItemProps> = ({
  link,
  currentNodeId,
  onNodeSelect,
}) => {
  const isOutgoing = link.source_node_id === currentNodeId;
  const targetNodeId = isOutgoing ? link.target_node_id : link.source_node_id;

  const {
    data: targetNode,
    isLoading,
    error,
  } = useNodeDetails(targetNodeId);

  const sourceMetadata = SOURCE_METADATA[link.source] || {
    label: link.source,
    color: 'gray',
    description: '',
  };

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
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </Card>
    );
  }

  if (error || !targetNode) {
    return (
      <Card>
        <div className="flex items-center gap-2 text-gray-500">
          <Info className="w-4 h-4" />
          <span>Node details unavailable</span>
          <code className="text-xs bg-gray-100 px-1 rounded">{targetNodeId}</code>
        </div>
      </Card>
    );
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="space-y-3">
        {/* Link relationship */}
        <div className="flex items-center gap-2 text-sm">
          <Badge color={sourceMetadata.color as any} size="sm">
            {sourceMetadata.label}
          </Badge>

          <div className="flex items-center gap-1 text-gray-600">
            {isOutgoing ? (
              <>
                <ArrowRight className="w-3 h-3" />
                <span className="font-medium">{link.predicate}</span>
              </>
            ) : (
              <>
                <ArrowLeft className="w-3 h-3" />
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
          <h4 className="font-semibold text-blue-600 cursor-pointer hover:text-blue-800 transition-colors">
            <button onClick={handleNodeClick} className="text-left">
              {targetNode.title}
            </button>
          </h4>

          {targetNode.definition && (
            <p className="text-sm text-gray-600 line-clamp-2">
              {targetNode.definition}
            </p>
          )}

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge
                color={
                  (SOURCE_METADATA[targetNode.source]?.color as any) || 'gray'
                }
                size="sm"
              >
                {SOURCE_METADATA[targetNode.source]?.label || targetNode.source}
              </Badge>
            </div>

            <div className="flex gap-1">
              <Button
                size="xs"
                color="blue"
                onClick={handleNodeClick}
              >
                View Details
              </Button>

              {targetNode.source_url && (
                <Button
                  size="xs"
                  color="gray"
                  onClick={() => window.open(targetNode.source_url, '_blank')}
                >
                  <ExternalLink className="w-3 h-3" />
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
  links,
  isLoading = false,
  error = null,
  onNodeSelect,
  showDirection = true,
}) => {
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [directionFilter, setDirectionFilter] = useState<'all' | 'outgoing' | 'incoming'>('all');
  const [predicateFilter, setPredicateFilter] = useState<string>('all');

  // Get unique values for filters
  const { sources, predicates, outgoingLinks, incomingLinks } = useMemo(() => {
    const sources = [...new Set(links.map(link => link.source))];
    const predicates = [...new Set(links.map(link => link.predicate))];
    const outgoing = links.filter(link => link.source_node_id === nodeId);
    const incoming = links.filter(link => link.target_node_id === nodeId);

    return {
      sources,
      predicates,
      outgoingLinks: outgoing,
      incomingLinks: incoming,
    };
  }, [links, nodeId]);

  // Filter links based on current filters
  const filteredLinks = useMemo(() => {
    return links.filter(link => {
      // Source filter
      if (sourceFilter !== 'all' && link.source !== sourceFilter) {
        return false;
      }

      // Direction filter
      if (directionFilter === 'outgoing' && link.source_node_id !== nodeId) {
        return false;
      }
      if (directionFilter === 'incoming' && link.target_node_id !== nodeId) {
        return false;
      }

      // Predicate filter
      if (predicateFilter !== 'all' && link.predicate !== predicateFilter) {
        return false;
      }

      return true;
    });
  }, [links, sourceFilter, directionFilter, predicateFilter, nodeId]);

  const clearFilters = () => {
    setSourceFilter('all');
    setDirectionFilter('all');
    setPredicateFilter('all');
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
            <h4 className="font-semibold flex items-center gap-2">
              <Filter className="w-4 h-4" />
              Filters
            </h4>

            <Button
              size="xs"
              color="gray"
              onClick={clearFilters}
              disabled={sourceFilter === 'all' && directionFilter === 'all' && predicateFilter === 'all'}
            >
              <RotateCcw className="w-3 h-3 mr-1" />
              Clear
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Direction filter */}
            {showDirection && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Direction
                </label>
                <Select
                  value={directionFilter}
                  onChange={(e) => setDirectionFilter(e.target.value as 'all' | 'outgoing' | 'incoming')}
                  sizing="sm"
                >
                  <option value="all">
                    All ({links.length})
                  </option>
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Source
              </label>
              <Select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                sizing="sm"
              >
                <option value="all">All Sources</option>
                {sources.map(source => (
                  <option key={source} value={source}>
                    {SOURCE_METADATA[source]?.label || source}
                  </option>
                ))}
              </Select>
            </div>

            {/* Predicate filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Relationship
              </label>
              <Select
                value={predicateFilter}
                onChange={(e) => setPredicateFilter(e.target.value)}
                sizing="sm"
              >
                <option value="all">All Relationships</option>
                {predicates.map(predicate => (
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
              <ArrowRight className="w-3 h-3" />
              {outgoingLinks.length} outgoing
            </span>
            <span className="flex items-center gap-1">
              <ArrowLeft className="w-3 h-3" />
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
              onNodeSelect={onNodeSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default LinkExplorer;
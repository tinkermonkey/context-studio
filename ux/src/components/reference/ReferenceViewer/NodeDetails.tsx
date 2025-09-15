/**
 * NodeDetails Component
 *
 * Detailed view of a unified reference node with links and metadata
 */

import React, { useState } from 'react';
import { Modal, Card, Badge, Button, Spinner, Alert } from 'flowbite-react';
import {
  ExternalLink,
  Copy,
  X,
  Calendar,
  Database,
  Link as LinkIcon,
  Info,
  CheckCircle,
} from 'lucide-react';
import { UnifiedNode } from '@/api/types/unified';
import { SOURCE_METADATA } from '@/api/types/unified';
import { useNodeDetails, useNodeLinks } from '@/api/hooks/unifiedReference/useUnifiedReference';
import { useReferenceStore, useSelectionState } from '@/store/referenceSlice';
import { DeduplicationIndicator } from '../UnifiedSearch/DeduplicationIndicator';
import { LinkExplorer } from './LinkExplorer';

interface NodeDetailsProps {
  node?: UnifiedNode;
  nodeId?: string;
  isOpen: boolean;
  onClose: () => void;
  onNodeSelect?: (node: UnifiedNode) => void;
}

export const NodeDetails: React.FC<NodeDetailsProps> = ({
  node: propNode,
  nodeId: propNodeId,
  isOpen,
  onClose,
  onNodeSelect,
}) => {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<number>(0);

  const { selectedNode } = useSelectionState();
  const { setShowNodeDetails } = useReferenceStore();

  // Use either the prop node or the selected node from store
  const targetNode = propNode || selectedNode;
  const targetNodeId = propNodeId || targetNode?.id;

  // Fetch node details if we only have an ID
  const {
    data: fetchedNode,
    isLoading: nodeLoading,
    error: nodeError,
  } = useNodeDetails(targetNodeId && !targetNode ? targetNodeId : null);

  // Fetch node links
  const {
    data: nodeLinks = [],
    isLoading: linksLoading,
    error: linksError,
  } = useNodeLinks(targetNodeId || null);

  const displayNode = targetNode || fetchedNode;

  const sourceMetadata = displayNode
    ? SOURCE_METADATA[displayNode.source] || {
        label: displayNode.source,
        color: 'gray',
        description: '',
      }
    : null;

  const handleClose = () => {
    setShowNodeDetails(false);
    onClose();
  };

  const handleCopyToClipboard = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };

  const CopyButton: React.FC<{ text: string; field: string }> = ({ text, field }) => (
    <Button
      size="xs"
      color="gray"
      onClick={() => handleCopyToClipboard(text, field)}
      className="opacity-60 hover:opacity-100 transition-opacity"
    >
      {copiedField === field ? (
        <CheckCircle className="w-3 h-3 text-green-600" />
      ) : (
        <Copy className="w-3 h-3" />
      )}
    </Button>
  );

  if (!isOpen) {
    return null;
  }

  return (
    <Modal show={isOpen} onClose={handleClose} size="4xl">
      <div className="flex items-center justify-between p-6 border-b">
        <h2 className="text-xl font-semibold">Node Details</h2>
        <Button
          color="gray"
          size="sm"
          onClick={handleClose}
          className="ml-auto"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      <div className="p-6">
        {nodeLoading && (
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
          </div>
        )}

        {nodeError && (
          <Alert color="failure" icon={Info}>
            Failed to load node details: {nodeError.message}
          </Alert>
        )}

        {displayNode && (
          <div className="space-y-6">
            {/* Header */}
            <div className="space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h1 className="text-2xl font-bold">{displayNode.title}</h1>
                    <CopyButton text={displayNode.title} field="title" />
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Badge color={sourceMetadata?.color as any} size="lg">
                      {sourceMetadata?.label}
                    </Badge>

                    {displayNode.confidence_score < 1 && (
                      <Badge color="gray">
                        {Math.round(displayNode.confidence_score * 100)}% match
                      </Badge>
                    )}

                    {displayNode.merged_from && displayNode.merged_from.length > 0 && (
                      <DeduplicationIndicator
                        mergedSources={displayNode.merged_from}
                        similarityScore={displayNode.confidence_score}
                        primarySource={displayNode.source}
                        showDetails={false}
                      />
                    )}
                  </div>
                </div>

                <div className="flex gap-2">
                  {displayNode.source_url && (
                    <Button
                      color="blue"
                      size="sm"
                      onClick={() => window.open(displayNode.source_url, '_blank')}
                    >
                      <ExternalLink className="w-4 h-4 mr-2" />
                      View Source
                    </Button>
                  )}
                </div>
              </div>

              {displayNode.definition && (
                <Card>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold">Definition</h3>
                      <CopyButton text={displayNode.definition} field="definition" />
                    </div>
                    <p className="text-gray-700 leading-relaxed">
                      {displayNode.definition}
                    </p>
                  </div>
                </Card>
              )}
            </div>

            {/* Simple Tab Navigation */}
            <div className="space-y-4">
              <div className="border-b border-gray-200">
                <nav className="-mb-px flex space-x-8">
                  <button
                    onClick={() => setActiveTab(0)}
                    className={`py-2 px-1 border-b-2 font-medium text-sm ${
                      activeTab === 0
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <LinkIcon className="w-4 h-4" />
                      Links ({nodeLinks.length})
                    </div>
                  </button>
                  <button
                    onClick={() => setActiveTab(1)}
                    className={`py-2 px-1 border-b-2 font-medium text-sm ${
                      activeTab === 1
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Database className="w-4 h-4" />
                      Metadata
                    </div>
                  </button>
                </nav>
              </div>

              {/* Tab Content */}
              {activeTab === 0 && (
                <LinkExplorer
                  nodeId={displayNode.id}
                  links={nodeLinks}
                  isLoading={linksLoading}
                  error={linksError}
                  onNodeSelect={onNodeSelect}
                />
              )}

              {activeTab === 1 && (
                <div className="space-y-4">
                  {/* Basic metadata */}
                  <Card>
                    <h4 className="font-semibold mb-3">Basic Information</h4>
                    <dl className="space-y-2">
                      <div className="flex justify-between">
                        <dt className="text-gray-600">ID:</dt>
                        <dd className="font-mono text-sm flex items-center gap-2">
                          {displayNode.id}
                          <CopyButton text={displayNode.id} field="id" />
                        </dd>
                      </div>

                      <div className="flex justify-between">
                        <dt className="text-gray-600">Source:</dt>
                        <dd>{sourceMetadata?.label}</dd>
                      </div>

                      <div className="flex justify-between">
                        <dt className="text-gray-600">Confidence:</dt>
                        <dd>{Math.round(displayNode.confidence_score * 100)}%</dd>
                      </div>

                      {displayNode.created_at && (
                        <div className="flex justify-between">
                          <dt className="text-gray-600">Created:</dt>
                          <dd className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            {new Date(displayNode.created_at).toLocaleDateString()}
                          </dd>
                        </div>
                      )}

                      {displayNode.updated_at && (
                        <div className="flex justify-between">
                          <dt className="text-gray-600">Updated:</dt>
                          <dd className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            {new Date(displayNode.updated_at).toLocaleDateString()}
                          </dd>
                        </div>
                      )}
                    </dl>
                  </Card>

                  {/* Deduplication info */}
                  {displayNode.merged_from && displayNode.merged_from.length > 0 && (
                    <Card>
                      <h4 className="font-semibold mb-3">Merged Sources</h4>
                      <DeduplicationIndicator
                        mergedSources={displayNode.merged_from}
                        similarityScore={displayNode.confidence_score}
                        primarySource={displayNode.source}
                        showDetails={true}
                      />
                    </Card>
                  )}

                  {/* Custom metadata */}
                  {displayNode.metadata && Object.keys(displayNode.metadata).length > 0 && (
                    <Card>
                      <h4 className="font-semibold mb-3">Additional Metadata</h4>
                      <dl className="space-y-2">
                        {Object.entries(displayNode.metadata).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <dt className="text-gray-600 capitalize">
                              {key.replace(/_/g, ' ')}:
                            </dt>
                            <dd className="text-right max-w-xs">
                              {typeof value === 'object'
                                ? JSON.stringify(value, null, 2)
                                : String(value)}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </Card>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default NodeDetails;
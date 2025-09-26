/**
 * NodeDetails Component
 *
 * Detailed view of a unified reference node with links and metadata
 */

import React, { useState } from "react";
import { Modal, Card, Badge, Button, Spinner, Alert } from "flowbite-react";
import {
  ExternalLink,
  Copy,
  X,
  Calendar,
  Database,
  Link as LinkIcon,
  Info,
  CheckCircle,
} from "lucide-react";
import { UnifiedNode, UnifiedSearchLink } from "@/api/types/unified";
import { SOURCE_METADATA } from "@/api/types/unified";
import {
  useNodeDetails,
} from "@/api/hooks/unifiedReference/useUnifiedReference";
import { LinkExplorer } from "./LinkExplorer";

interface NodeDetailsProps {
  node?: UnifiedNode;
  nodeId?: string;
  isOpen: boolean;
  onClose: () => void;
  onNodeSelect?: (node: UnifiedNode) => void;
  searchLinks?: UnifiedSearchLink[];
  searchResults?: UnifiedNode[];
}

export const NodeDetails: React.FC<NodeDetailsProps> = ({
  node: propNode,
  nodeId: propNodeId,
  isOpen,
  onClose,
  onNodeSelect,
  searchLinks = [],
  searchResults = [],
}) => {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<number>(0);

  // Use either the prop node or the node ID
  const targetNode = propNode;
  const targetNodeId = propNodeId || targetNode?.id;

  // Fetch node details if we only have an ID
  const {
    data: fetchedNode,
    isLoading: nodeLoading,
    error: nodeError,
  } = useNodeDetails(targetNodeId && !targetNode ? targetNodeId : null);

  // Filter search links for the current node (either as subject or object)
  const nodeLinks = targetNodeId || targetNode?.id
    ? searchLinks.filter(link =>
        link.subject === (targetNodeId || targetNode?.id) ||
        link.object === (targetNodeId || targetNode?.id)
      )
    : [];
  const linksLoading = false; // No async loading needed for search links
  const linksError = null;

  const displayNode = targetNode || fetchedNode;

  const sourceMetadata = displayNode
    ? SOURCE_METADATA[displayNode.source] || {
        label: displayNode.source,
        color: "gray",
        description: "",
      }
    : null;

  const handleClose = () => {
    onClose();
  };

  const handleCopyToClipboard = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (error) {
      console.error("Failed to copy to clipboard:", error);
    }
  };

  const CopyButton: React.FC<{ text: string; field: string }> = ({
    text,
    field,
  }) => (
    <Button
      size="xs"
      color="gray"
      onClick={() => handleCopyToClipboard(text, field)}
      className="opacity-60 transition-opacity hover:opacity-100"
    >
      {copiedField === field ? (
        <CheckCircle className="h-3 w-3 text-green-600" />
      ) : (
        <Copy className="h-3 w-3" />
      )}
    </Button>
  );

  if (!isOpen) {
    return null;
  }

  return (
    <Modal show={isOpen} onClose={handleClose} size="4xl">
      <div className="flex items-center justify-between border-b p-6">
        <h2 className="text-xl font-semibold">Node Details</h2>
        <Button
          color="gray"
          size="sm"
          onClick={handleClose}
          className="ml-auto"
        >
          <X className="h-4 w-4" />
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
                  <div className="mb-2 flex items-center gap-2">
                    <h1 className="text-2xl font-bold">{displayNode.title}</h1>
                    <CopyButton text={displayNode.title} field="title" />
                  </div>

                  <div className="mb-3 flex items-center gap-2">
                    <span className="text-sm text-gray-600">ID:</span>
                    <code className="rounded bg-gray-100 px-2 py-1 text-sm font-mono text-gray-800">
                      {displayNode.id}
                    </code>
                    <CopyButton text={displayNode.id} field="header-id" />
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Badge color={sourceMetadata?.color as any} size="lg">
                      {sourceMetadata?.label}
                    </Badge>

                    {displayNode.relevance_score !== undefined && displayNode.relevance_score < 1 && (
                      <Badge color="gray">
                        {Math.round(displayNode.relevance_score * 100)}% match
                      </Badge>
                    )}

                    {/* Merged sources badge removed in normalized API */}
                  </div>
                </div>

                <div className="flex gap-2">
                  {displayNode.source_url && (
                    <Button
                      color="blue"
                      size="sm"
                      onClick={() =>
                        window.open(displayNode.source_url, "_blank")
                      }
                    >
                      <ExternalLink className="mr-2 h-4 w-4" />
                      View Source
                    </Button>
                  )}
                </div>
              </div>

              <Card>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold">Definition</h3>
                    {displayNode.definition && (
                      <CopyButton
                        text={displayNode.definition}
                        field="definition"
                      />
                    )}
                  </div>
                  <p className="leading-relaxed text-gray-700">
                    {displayNode.definition || (
                      <span className="italic text-gray-500">
                        No definition available for this node.
                      </span>
                    )}
                  </p>
                </div>
              </Card>
            </div>

            {/* Simple Tab Navigation */}
            <div className="space-y-4">
              <div className="border-b border-gray-200">
                <nav className="-mb-px flex space-x-8">
                  <button
                    onClick={() => setActiveTab(0)}
                    className={`border-b-2 px-1 py-2 text-sm font-medium ${
                      activeTab === 0
                        ? "border-blue-500 text-blue-600"
                        : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <LinkIcon className="h-4 w-4" />
                      Links ({nodeLinks.length})
                    </div>
                  </button>
                  <button
                    onClick={() => setActiveTab(1)}
                    className={`border-b-2 px-1 py-2 text-sm font-medium ${
                      activeTab === 1
                        ? "border-blue-500 text-blue-600"
                        : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Database className="h-4 w-4" />
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
                  searchResults={searchResults}
                  isLoading={linksLoading}
                  error={linksError}
                  onNodeSelect={onNodeSelect}
                />
              )}

              {activeTab === 1 && (
                <div className="space-y-4">
                  {/* Basic metadata */}
                  <Card>
                    <h4 className="mb-3 font-semibold">Basic Information</h4>
                    <dl className="space-y-2">
                      <div className="flex justify-between">
                        <dt className="text-gray-600">ID:</dt>
                        <dd className="flex items-center gap-2 font-mono text-sm">
                          {displayNode.id}
                          <CopyButton text={displayNode.id} field="id" />
                        </dd>
                      </div>

                      <div className="flex justify-between">
                        <dt className="text-gray-600">Source:</dt>
                        <dd>{sourceMetadata?.label}</dd>
                      </div>

                      {displayNode.relevance_score !== undefined && (
                        <div className="flex justify-between">
                          <dt className="text-gray-600">Confidence:</dt>
                          <dd>
                            {Math.round(displayNode.relevance_score * 100)}%
                          </dd>
                        </div>
                      )}

                      {null && (
                        <div className="flex justify-between">
                          <dt className="text-gray-600">Created:</dt>
                          <dd className="flex items-center gap-1">
                            <Calendar className="h-4 w-4" />
                            {new Date(
                              null,
                            ).toLocaleDateString()}
                          </dd>
                        </div>
                      )}

                      {null && (
                        <div className="flex justify-between">
                          <dt className="text-gray-600">Updated:</dt>
                          <dd className="flex items-center gap-1">
                            <Calendar className="h-4 w-4" />
                            {new Date(
                              null,
                            ).toLocaleDateString()}
                          </dd>
                        </div>
                      )}
                    </dl>
                  </Card>

                  {/* Deduplication info removed in normalized API */}

                  {/* Custom metadata */}
                  {displayNode.attributes &&
                    Object.keys(displayNode.attributes).length > 0 && (
                      <Card>
                        <h4 className="mb-3 font-semibold">
                          Additional Metadata
                        </h4>
                        <dl className="space-y-2">
                          {Object.entries(displayNode.attributes).map(
                            ([key, value]) => (
                              <div key={key} className="flex justify-between">
                                <dt className="text-gray-600 capitalize">
                                  {key.replace(/_/g, " ")}:
                                </dt>
                                <dd className="max-w-xs text-right">
                                  {typeof value === "object"
                                    ? JSON.stringify(value, null, 2)
                                    : String(value)}
                                </dd>
                              </div>
                            ),
                          )}
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

/**
 * NodeLinkPanel Component
 *
 * Main container for managing node links.
 * Provides inline form for creating links and displays existing links.
 */

import React, { useState } from "react";
import { Button, Alert } from "flowbite-react";
import { Plus, Info } from "lucide-react";

import { OntologyClass } from "@/api/types/ontology";
import { useRelationships } from "@/api/hooks/relationships";
import { NodeLinkForm } from "./NodeLinkForm";
import { NodeLinkDisplay } from "./NodeLinkDisplay";

export interface NodeLinkPanelProps {
  nodeId: string;
  node: OntologyClass;
}

export const NodeLinkPanel: React.FC<NodeLinkPanelProps> = ({
  nodeId,
  node,
}) => {
  const [isFormActive, setIsFormActive] = useState(false);

  // Fetch relationships filtered for this node only
  const {
    data: links = [],
    isLoading,
    error,
  } = useRelationships({
    source_id: nodeId,
  });

  const hasLinks = links.length > 0;
  const shouldShowForm = isFormActive;

  const handleSuccess = () => {
    setIsFormActive(false);
  };

  const handleCancel = () => {
    setIsFormActive(false);
  };

  const handleAddLink = () => {
    setIsFormActive(true);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Node Links</h2>
        {!isFormActive && hasLinks && (
          <Button size="sm" color="gray" onClick={() => setIsFormActive(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Link
          </Button>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <Alert color="info" icon={Info}>
          Loading links...
        </Alert>
      )}

      {/* Error State */}
      {error && (
        <Alert color="failure">Failed to load links: {error.message}</Alert>
      )}

      {/* Form - shown when active */}
      {shouldShowForm && !isLoading && !error && (
        <NodeLinkForm
          currentNode={node}
          existingLinks={links}
          onSuccess={handleSuccess}
          onCancel={handleCancel}
        />
      )}

      {/* Display Links */}
      {!isLoading && !error && hasLinks && (
        <>
          {isFormActive && (
            <div className="border-t pt-4">
              <h3 className="mb-3 text-lg font-medium">
                Current Links ({links.length})
              </h3>
            </div>
          )}
          <NodeLinkDisplay links={links} currentNodeId={nodeId} />
        </>
      )}

      {/* Cancel Button - shown when form active and links exist */}
      {isFormActive && hasLinks && (
        <div className="flex justify-end border-t pt-4">
          <Button size="sm" color="gray" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
      )}

      {/* Empty State - shown when no links and form not active */}
      {!isLoading && !error && !hasLinks && !isFormActive && (
        <Alert color="info" icon={Info}>
          <div className="flex items-center justify-between">
            <span>No links for this node.</span>
            <Button size="sm" color="blue" onClick={handleAddLink}>
              <Plus className="mr-2 h-4 w-4" />
              Add Link
            </Button>
          </div>
        </Alert>
      )}
    </div>
  );
};

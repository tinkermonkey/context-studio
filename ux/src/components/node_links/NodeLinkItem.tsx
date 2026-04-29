/**
 * NodeLinkItem Component
 *
 * Displays a single node link with navigation and delete functionality
 */

import React, { useState } from "react";
import {
  Button,
  Modal,
  ModalHeader,
  ModalBody,
  Alert,
  Spinner,
} from "flowbite-react";
import { AlertCircle, Database, Hash, Layers, Trash2 } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";

import { OntologyClassLink, NodeType } from "@/api/types/ontology";
import { useOntologyClass } from "@/api/hooks/ontologyClasses";

interface NodeLinkItemProps {
  link: OntologyClassLink;
  currentNodeId: string;
  onDelete: (linkId: string) => void;
  isDeleting: boolean;
}

export const NodeLinkItem: React.FC<NodeLinkItemProps> = ({
  link,
  currentNodeId,
  onDelete,
  isDeleting,
}) => {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const navigate = useNavigate();

  // Determine which node to display (the "other" node, not the current one)
  const isOutgoing = link.source_id === currentNodeId;
  const displayNodeId = isOutgoing ? link.target_id : link.source_id;

  // Fetch the node to display
  const { data: displayNode, isLoading } = useOntologyClass(displayNodeId);

  const handleDelete = () => {
    onDelete(link.id);
  };

  const handleNavigate = () => {
    navigate({ to: `/app/ontologyClass/${displayNodeId}` });
  };

  // Get icon for node type
  const getNodeIcon = (nodeType?: string | NodeType) => {
    switch (nodeType) {
      case "taxonomy":
      case NodeType.TAXONOMY:
        return Layers;
      case "concept_scheme":
      case "scheme":
      case NodeType.CONCEPT_SCHEME:
        return Database;
      case "class":
      case NodeType.CLASS:
        return Hash;
      default:
        return Hash;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border bg-gray-50 p-3">
        <Spinner size="sm" />
        <span className="text-sm text-gray-500">Loading...</span>
      </div>
    );
  }

  if (!displayNode) {
    return (
      <div className="flex items-center gap-2 rounded-lg border bg-gray-50 p-3">
        <span className="text-sm text-gray-500">Node not found</span>
      </div>
    );
  }

  const NodeIcon = getNodeIcon(displayNode.node_type);

  return (
    <>
      <div className="flex items-center justify-between rounded-lg border bg-gray-50 p-3 transition-colors hover:bg-gray-100">
        <button
          onClick={handleNavigate}
          className="flex flex-1 cursor-pointer items-center gap-2 text-left hover:text-blue-600"
          aria-label={`Navigate to ${displayNode.title}`}
        >
          <NodeIcon className="h-4 w-4 flex-shrink-0" />
          <span className="font-medium">{displayNode.title}</span>
          <span className="text-sm text-gray-500">
            ({displayNode.node_type})
          </span>
        </button>
        <Button
          size="xs"
          color="failure"
          onClick={() => setConfirmDelete(true)}
          disabled={isDeleting}
          aria-label={`Remove link to ${displayNode.title}`}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Confirmation Modal */}
      <Modal
        show={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        size="md"
      >
        <ModalHeader>Confirm Deletion</ModalHeader>
        <ModalBody>
          <div className="space-y-4">
            <Alert color="warning" icon={AlertCircle}>
              <p className="text-sm">
                Are you sure you want to delete this link?
              </p>
            </Alert>

            <div className="rounded-lg border bg-gray-50 p-3">
              <div className="mb-2 flex items-center gap-2">
                <NodeIcon className="h-4 w-4" />
                <span className="font-medium">{displayNode.title}</span>
                <span className="text-sm text-gray-500">
                  ({displayNode.node_type})
                </span>
              </div>
              <div className="text-sm text-gray-600">
                via:{" "}
                <code className="font-mono">{link.property_definition_id}</code>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button
                color="gray"
                onClick={() => setConfirmDelete(false)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                color="failure"
                onClick={() => {
                  handleDelete();
                  setConfirmDelete(false);
                }}
                disabled={isDeleting}
              >
                {isDeleting ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </>
                )}
              </Button>
            </div>
          </div>
        </ModalBody>
      </Modal>
    </>
  );
};

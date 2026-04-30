/**
 * ReferenceNodeSelectionList Component
 *
 * Staging area for selected reference nodes before saving.
 * Shows source badges and allows removal before persisting.
 */

import React from "react";
import { Alert, Badge, Button, Spinner } from "flowbite-react";
import { Save, Trash2, X } from "lucide-react";

import { UnifiedNode } from "@/api/types/unified";
import { ReferenceLink } from "@/api/services/reference";
import { useAddReferenceLinks } from "@/api/hooks/ontologyClasses/useReferenceLinks";
import { getSourceBadgeColor, getSourceLabel } from "@/utils/sourceUtils";
import { toast } from "@/utils/toast";

interface ReferenceNodeSelectionListProps {
  nodeId: string;
  selectedNodes: UnifiedNode[];
  onRemoveNode: (node: UnifiedNode) => void;
  onClearAll: () => void;
  onSaveSuccess: () => void;
}

export const ReferenceNodeSelectionList: React.FC<
  ReferenceNodeSelectionListProps
> = ({ nodeId, selectedNodes, onRemoveNode, onClearAll, onSaveSuccess }) => {
  const addReferenceLinks = useAddReferenceLinks(nodeId, {
    onSuccess: () => {
      toast.success(
        `Successfully added ${selectedNodes.length} reference link${
          selectedNodes.length !== 1 ? "s" : ""
        }`,
      );
      onSaveSuccess();
    },
    onError: (error: Error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to save reference links",
      );
    },
  });

  const handleSave = () => {
    // Convert UnifiedNodes to ReferenceLinks
    const referenceLinks: ReferenceLink[] = selectedNodes.map((node) => ({
      id: node.id,
      source: node.source,
      external_id: node.id,
    }));

    addReferenceLinks.mutate(referenceLinks);
  };

  if (selectedNodes.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 border-t pt-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">
          Selected References ({selectedNodes.length})
        </h3>
        <div className="flex gap-2">
          <Button
            size="sm"
            color="gray"
            onClick={onClearAll}
            disabled={addReferenceLinks.isPending}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Clear All
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={addReferenceLinks.isPending}
          >
            {addReferenceLinks.isPending ? (
              <>
                <Spinner size="sm" className="mr-2" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save
              </>
            )}
          </Button>
        </div>
      </div>

      {addReferenceLinks.isPending && (
        <Alert color="info">
          <div className="flex items-center gap-2">
            <Spinner size="sm" />
            <span>Saving reference links...</span>
          </div>
        </Alert>
      )}

      <div className="space-y-2">
        {selectedNodes.map((node) => {
          const nodeKey = `${node.source}-${node.id}`;
          const relevancePercent = Math.round(
            (node.relevance_score || 0) * 100,
          );

          return (
            <div
              key={nodeKey}
              className="flex items-start gap-3 rounded-lg border bg-gray-50 p-3"
            >
              <div className="flex-1">
                <h4 className="font-medium text-gray-900">{node.title}</h4>
                {node.definition && (
                  <p className="mt-1 line-clamp-2 text-sm text-gray-600">
                    {node.definition}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge color={getSourceBadgeColor(node.source)}>
                    {getSourceLabel(node.source)}
                  </Badge>
                  <Badge color="gray" size="sm">
                    ID: {node.id}
                  </Badge>
                  {(node.relevance_score || 0) < 1 && (
                    <Badge color="gray" size="sm">
                      {relevancePercent}% match
                    </Badge>
                  )}
                </div>
              </div>
              <Button
                size="xs"
                color="gray"
                onClick={() => onRemoveNode(node)}
                disabled={addReferenceLinks.isPending}
                className="flex-shrink-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ReferenceNodeSelectionList;

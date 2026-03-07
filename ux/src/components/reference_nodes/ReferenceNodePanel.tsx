/**
 * ReferenceNodePanel Component
 *
 * Container component that manages state for reference node search, selection, and display.
 * Coordinates between search interface and persisted reference display.
 */

import React, { useState } from "react";
import { Button, Alert } from "flowbite-react";
import { Search, Info } from "lucide-react";

import { UnifiedNode } from "@/api/types/unified";
import { useReferenceLinks } from "@/api/hooks/structure_nodes/useReferenceLinks";
import { ReferenceNodeSearch } from "./ReferenceNodeSearch";
import { ReferenceNodeSelectionList } from "./ReferenceNodeSelectionList";
import { ReferenceNodeDisplay } from "./ReferenceNodeDisplay";

interface ReferenceNodePanelProps {
  nodeId: string;
  nodeTitle?: string;
}

// UUID validation regex
const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const ReferenceNodePanel: React.FC<ReferenceNodePanelProps> = ({
  nodeId,
  nodeTitle,
}) => {
  const [isSearchActive, setIsSearchActive] = useState(false);
  const [selectedNodes, setSelectedNodes] = useState<UnifiedNode[]>([]);

  // Validate UUID format before making API calls
  const isValidUuid = UUID_REGEX.test(nodeId);

  // Fetch persisted reference links only if UUID is valid
  const {
    data: persistedLinks = [],
    isLoading: linksLoading,
    error: linksError,
  } = useReferenceLinks(isValidUuid ? nodeId : "");

  // Handle adding a node to the selection list
  const handleAddNode = (node: UnifiedNode) => {
    // Check if node is already selected
    const isAlreadySelected = selectedNodes.some(
      (n) => n.id === node.id && n.source === node.source,
    );
    if (!isAlreadySelected) {
      setSelectedNodes([...selectedNodes, node]);
    }
  };

  // Handle removing a node from the selection list
  const handleRemoveNode = (node: UnifiedNode) => {
    setSelectedNodes(
      selectedNodes.filter(
        (n) => !(n.id === node.id && n.source === node.source),
      ),
    );
  };

  // Handle clearing all selections
  const handleClearAll = () => {
    setSelectedNodes([]);
  };

  // Handle successful save
  const handleSaveSuccess = () => {
    setSelectedNodes([]);
    setIsSearchActive(false);
  };

  const hasPersistedLinks = persistedLinks.length > 0;
  const hasSelections = selectedNodes.length > 0;
  const shouldShowSearch =
    isSearchActive || (!hasPersistedLinks && !hasSelections);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xl font-semibold">
          Reference Nodes
        </h2>
        {!isSearchActive && hasPersistedLinks && (
          <Button
            size="sm"
            color="gray"
            onClick={() => setIsSearchActive(true)}
          >
            <Search className="mr-2 h-4 w-4" />
            Add References
          </Button>
        )}
      </div>

      {/* Invalid UUID State */}
      {!isValidUuid && (
        <Alert color="failure">
          Invalid node ID format. Cannot load reference links.
        </Alert>
      )}

      {/* Loading State */}
      {isValidUuid && linksLoading && (
        <Alert color="info" icon={Info}>
          Loading reference links...
        </Alert>
      )}

      {/* Error State */}
      {isValidUuid && linksError && (
        <Alert color="failure">
          Failed to load reference links: {linksError.message}
        </Alert>
      )}

      {/* Search Interface */}
      {isValidUuid && shouldShowSearch && !linksLoading && (
        <ReferenceNodeSearch
          onAddNode={handleAddNode}
          selectedNodes={selectedNodes}
          defaultSearchQuery={nodeTitle}
        />
      )}

      {/* Selection List */}
      {isValidUuid && hasSelections && (
        <ReferenceNodeSelectionList
          nodeId={nodeId}
          selectedNodes={selectedNodes}
          onRemoveNode={handleRemoveNode}
          onClearAll={handleClearAll}
          onSaveSuccess={handleSaveSuccess}
        />
      )}

      {/* Persisted Reference Display */}
      {hasPersistedLinks && !linksLoading && (
        <>
          {isSearchActive && (
            <div className="border-t pt-4">
              <h3 className="mb-3 text-lg font-medium">
                Current References ({persistedLinks.length})
              </h3>
            </div>
          )}
          <ReferenceNodeDisplay
            nodeId={nodeId}
            referenceLinks={persistedLinks}
          />
        </>
      )}

      {/* Empty State */}
      {!hasPersistedLinks &&
        !isSearchActive &&
        !hasSelections &&
        !linksLoading && (
          <Alert color="info" icon={Info}>
            <div className="space-y-2">
              <p className="font-medium">No reference nodes associated</p>
            </div>
          </Alert>
        )}

      {/* Cancel Search Button */}
      {isSearchActive && hasPersistedLinks && (
        <div className="flex justify-end border-t pt-4">
          <Button
            size="sm"
            color="gray"
            onClick={() => {
              setIsSearchActive(false);
              setSelectedNodes([]);
            }}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
};

export default ReferenceNodePanel;

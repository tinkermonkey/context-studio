/**
 * ReferenceNodePanel Component
 *
 * Container component that manages state for reference node search, selection, and display.
 * Coordinates between search interface and persisted reference display.
 */

import React, { useState } from "react";
import { Card, Button, Alert } from "flowbite-react";
import { Link as LinkIcon, Search, Info } from "lucide-react";
import { ReferenceLink } from "@/api/types/structureNodes";
import { UnifiedNode } from "@/api/types/unified";
import { useReferenceLinks } from "@/api/hooks/structure_nodes/useReferenceLinks";
import { ReferenceNodeSearch } from "./ReferenceNodeSearch";
import { ReferenceNodeSelectionList } from "./ReferenceNodeSelectionList";
import { ReferenceNodeDisplay } from "./ReferenceNodeDisplay";

interface ReferenceNodePanelProps {
  nodeId: string;
}

export const ReferenceNodePanel: React.FC<ReferenceNodePanelProps> = ({
  nodeId,
}) => {
  const [isSearchActive, setIsSearchActive] = useState(false);
  const [selectedNodes, setSelectedNodes] = useState<UnifiedNode[]>([]);

  // Fetch persisted reference links
  const {
    data: persistedLinks = [],
    isLoading: linksLoading,
    error: linksError,
  } = useReferenceLinks(nodeId);

  // Handle adding a node to the selection list
  const handleAddNode = (node: UnifiedNode) => {
    // Check if node is already selected
    const isAlreadySelected = selectedNodes.some(
      (n) => n.id === node.id && n.source === node.source
    );
    if (!isAlreadySelected) {
      setSelectedNodes([...selectedNodes, node]);
    }
  };

  // Handle removing a node from the selection list
  const handleRemoveNode = (node: UnifiedNode) => {
    setSelectedNodes(
      selectedNodes.filter(
        (n) => !(n.id === node.id && n.source === node.source)
      )
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
  const shouldShowSearch = isSearchActive || (!hasPersistedLinks && !hasSelections);

  return (
    <Card>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-xl font-semibold">
            <LinkIcon className="h-5 w-5" />
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

        {/* Loading State */}
        {linksLoading && (
          <Alert color="info" icon={Info}>
            Loading reference links...
          </Alert>
        )}

        {/* Error State */}
        {linksError && (
          <Alert color="failure">
            Failed to load reference links: {linksError.message}
          </Alert>
        )}

        {/* Search Interface */}
        {shouldShowSearch && !linksLoading && (
          <ReferenceNodeSearch
            onAddNode={handleAddNode}
            selectedNodes={selectedNodes}
          />
        )}

        {/* Selection List */}
        {hasSelections && (
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
            <ReferenceNodeDisplay nodeId={nodeId} referenceLinks={persistedLinks} />
          </>
        )}

        {/* Empty State */}
        {!hasPersistedLinks && !isSearchActive && !hasSelections && !linksLoading && (
          <Alert color="info" icon={Info}>
            <div className="space-y-2">
              <p className="font-medium">No reference nodes associated</p>
              <p className="text-sm">
                Search external reference sources to link this node to related concepts.
              </p>
              <Button
                size="sm"
                color="blue"
                onClick={() => setIsSearchActive(true)}
                className="mt-2"
              >
                <Search className="mr-2 h-4 w-4" />
                Search References
              </Button>
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
    </Card>
  );
};

export default ReferenceNodePanel;

/**
 * Domain Move Form
 *
 * Form for moving domains between layers
 */

import React, { useState } from "react";
import { Button, Label, Checkbox } from "flowbite-react";
import { StructureNode } from "@/api/types/structureNodes";
import { LayerSelector } from "@/components/node_selectors/layer_selector";
import { useUpdateStructureNode } from "@/api/hooks/structure_nodes/useStructureNodeMutations";

interface DomainMoveFormProps {
  selectedNodes: StructureNode[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function DomainMoveForm({
  selectedNodes,
  onSuccess,
  onCancel,
}: DomainMoveFormProps) {
  const [targetLayerId, setTargetLayerId] = useState<string>("");
  const [moveTerms, setMoveTerms] = useState(true);
  const updateDomain = useUpdateStructureNode();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!targetLayerId) {
      return;
    }

    try {
      // Move each domain individually using the structure node update API
      await Promise.all(
        selectedNodes.map((domain) =>
          updateDomain.mutateAsync({
            id: domain.id,
            data: {
              parent_node_id: targetLayerId,
            },
          }),
        ),
      );

      onSuccess();
    } catch (error) {
      console.error("Failed to move domains:", error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="target-layer">Target Layer</Label>
        <LayerSelector
          value={targetLayerId}
          onSelect={(layer) => setTargetLayerId(layer?.id || "")}
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="move-terms"
          checked={moveTerms}
          onChange={(e) => setMoveTerms(e.target.checked)}
        />
        <Label htmlFor="move-terms" className="text-sm">
          Also move all terms contained in these domains
        </Label>
      </div>

      <div className="text-sm text-gray-600">
        Moving {selectedNodes.length} domain
        {selectedNodes.length > 1 ? "s" : ""} to a new layer.
        {moveTerms && " All terms in these domains will also be moved."}
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button type="button" color="gray" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          color="blue"
          disabled={!targetLayerId || moveDomains.isPending}
        >
          {moveDomains.isPending ? "Moving..." : "Move Domains"}
        </Button>
      </div>
    </form>
  );
}

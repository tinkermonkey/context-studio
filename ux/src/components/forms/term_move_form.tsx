/**
 * Term Move Form
 *
 * Form for moving terms between domains
 */

import React, { useState } from "react";
import { Button, Label, Checkbox } from "flowbite-react";
import { StructureNode } from "@/api/types/structureNodes";
import { DomainSelector } from "@/components/node_selectors/domain_selector";
import { useUpdateStructureNode } from "@/api/hooks/structure_nodes/useStructureNodeMutations";

interface TermMoveFormProps {
  selectedNodes: StructureNode[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function TermMoveForm({
  selectedNodes,
  onSuccess,
  onCancel,
}: TermMoveFormProps) {
  const [targetDomainId, setTargetDomainId] = useState<string>("");
  const [moveChildren, setMoveChildren] = useState(true);
  const updateTerm = useUpdateStructureNode();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!targetDomainId) {
      return;
    }

    try {
      // Move each term individually using the structure node update API
      await Promise.all(
        selectedNodes.map((term) =>
          updateTerm.mutateAsync({
            id: term.id,
            data: {
              parent_node_id: targetDomainId,
            },
          }),
        ),
      );

      onSuccess();
    } catch (error) {
      console.error("Failed to move terms:", error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="z-10 space-y-4">
      <div>
        <Label htmlFor="target-domain">Target Domain</Label>
        <DomainSelector
          value={targetDomainId}
          onSelect={(domain) => setTargetDomainId(domain?.id || "")}
          className="z-10"
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="move-children"
          checked={moveChildren}
          onChange={(e) => setMoveChildren(e.target.checked)}
        />
        <Label htmlFor="move-children" className="text-sm">
          Also move all child terms recursively
        </Label>
      </div>

      <div className="text-sm text-gray-600">
        Moving {selectedNodes.length} term{selectedNodes.length > 1 ? "s" : ""}{" "}
        to a new domain.
        {moveChildren && " All child terms will also be moved recursively."}
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button type="button" color="gray" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          color="blue"
          disabled={!targetDomainId || moveTerms.isPending}
        >
          {moveTerms.isPending ? "Moving..." : "Move Terms"}
        </Button>
      </div>
    </form>
  );
}

/**
 * Class Move Form
 *
 * Form for moving classes to different hierarchy levels
 */

import React, { useState } from "react";
import { Button, Label, Checkbox, Alert } from "flowbite-react";
import { Info } from "lucide-react";
import { OntologyClass } from "@/api/types/ontology";
import { OntologyClassSelector } from "@/components/node_selectors/structure_node_selector";
import { useMoveOntologyClass } from "@/api/hooks/ontologyClasses/useOntologyClassMutations";
import { useButterToast } from "@/hooks/useButterToast";

interface ClassMoveFormProps {
  selectedNodes: OntologyClass[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function ClassMoveForm({
  selectedNodes,
  onSuccess,
  onCancel,
}: ClassMoveFormProps) {
  const [targetParentId, setTargetParentId] = useState<string>("");
  const [moveChildren, setMoveChildren] = useState(true);
  const moveNodes = useMoveOntologyClass();
  const toast = useButterToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!targetParentId) {
      return;
    }

    try {
      const result = await moveNodes.mutateAsync({
        node_ids: selectedNodes.map((node) => node.id),
        target_parent_id: targetParentId,
        move_children: moveChildren,
        handle_conflicts: "warn",
      });

      let message = `Moved ${result.moved_nodes.length} class(es) successfully`;
      if (result.converted_nodes.length > 0) {
        message += ` (${result.converted_nodes.length} node(s) had type automatically converted)`;
      }
      toast.success(message);

      if (result.warnings.length > 0) {
        result.warnings.forEach((warning: string) => toast.warning(warning));
      }

      onSuccess();
    } catch (error) {
      console.error("Failed to move classes:", error);
      toast.error("Failed to move nodes. Please try again.");
    }
  };

  const excludeNodeIds = selectedNodes.map((node) => node.id);

  return (
    <form onSubmit={handleSubmit} className="z-10 space-y-4">
      <Alert color="info" icon={Info}>
        <span className="font-medium">Move Classes</span>
        <p className="mt-1 text-sm">
          Moving classes to a different concept scheme or parent class.
        </p>
      </Alert>

      <div>
        <Label htmlFor="target-parent">Target Parent Node</Label>
        <OntologyClassSelector
          value={targetParentId}
          onSelect={(node) => setTargetParentId(node?.id || "")}
          excludeNodeIds={excludeNodeIds}
          placeholder="Select target parent"
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="move-children"
          checked={moveChildren}
          onChange={(e) => setMoveChildren(e.target.checked)}
        />
        <Label htmlFor="move-children" className="text-sm">
          Also move all child classes recursively
        </Label>
      </div>

      <div className="text-sm text-gray-600">
        Moving {selectedNodes.length} class{selectedNodes.length > 1 ? "es" : ""}.
        {moveChildren && " All child classes will also be moved recursively."}
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button type="button" color="gray" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          color="blue"
          disabled={!targetParentId || moveNodes.isPending}
        >
          {moveNodes.isPending ? "Moving..." : "Move Classes"}
        </Button>
      </div>
    </form>
  );
}

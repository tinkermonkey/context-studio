/**
 * Term Move Form
 *
 * Form for moving terms to different hierarchy levels with automatic type conversion
 */

import React, { useState } from "react";
import { Button, Label, Checkbox, Alert } from "flowbite-react";
import { Info } from "lucide-react";
import { OntologyClass } from "@/api/types/ontology";
import { OntologyClassSelector } from "@/components/node_selectors/structure_node_selector";
import { useMoveOntologyClass } from "@/api/hooks/ontologyClasses/useOntologyClassMutations";
import { useButterToast } from "@/hooks/useButterToast";

interface TermMoveFormProps {
  selectedNodes: OntologyClass[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function TermMoveForm({
  selectedNodes,
  onSuccess,
  onCancel,
}: TermMoveFormProps) {
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

      // Show success message with conversion info
      let message = `Moved ${result.moved_nodes.length} node(s) successfully`;
      if (result.converted_nodes.length > 0) {
        message += ` (${result.converted_nodes.length} node(s) had type automatically converted)`;
      }
      toast.success(message);

      // Show warnings if any
      if (result.warnings.length > 0) {
        result.warnings.forEach((warning: string) => toast.warning(warning));
      }

      onSuccess();
    } catch (error) {
      console.error("Failed to move terms:", error);
      const message =
        error instanceof Error ? error.message : "Failed to move nodes";
      toast.error(message);
    }
  };

  const excludeNodeIds = selectedNodes.map((node) => node.id);

  return (
    <form onSubmit={handleSubmit} className="z-10 space-y-4">
      {/* Informational Alert about Type Conversion */}
      <Alert color="info" icon={Info}>
        <span className="font-medium">Automatic Type Conversion</span>
        <p className="mt-1 text-sm">
          Moving to a different hierarchy level will automatically convert node
          types:
        </p>
        <ul className="mt-2 ml-4 list-disc text-sm">
          <li>Moving to root (no parent) → becomes a layer</li>
          <li>Moving under a layer → becomes a domain</li>
          <li>Moving under a domain or term → becomes a term</li>
          <li>All child nodes will be converted recursively</li>
        </ul>
      </Alert>

      <div>
        <Label htmlFor="target-parent">Target Parent Node</Label>
        <OntologyClassSelector
          value={targetParentId}
          onSelect={(node) => setTargetParentId(node?.id || "")}
          excludeNodeIds={excludeNodeIds}
          placeholder="Select target parent (or leave empty for root)"
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="move-children"
          checked={moveChildren}
          onChange={(e) => setMoveChildren(e.target.checked)}
        />
        <Label htmlFor="move-children" className="text-sm">
          Also move all child nodes recursively
        </Label>
      </div>

      <div className="text-sm text-gray-600">
        Moving {selectedNodes.length} node{selectedNodes.length > 1 ? "s" : ""}.
        {moveChildren && " All child nodes will also be moved recursively."}
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
          {moveNodes.isPending ? "Moving..." : "Move Nodes"}
        </Button>
      </div>
    </form>
  );
}

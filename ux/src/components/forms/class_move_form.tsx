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
import { useButterToast } from "@/hooks/useButterToast";

/**
 * @deprecated Move functionality is not yet supported by the backend
 * This component is kept for future implementation when the API is available
 */

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
  const toast = useButterToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    toast.error("Move functionality is not yet available");
    onCancel();
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
        Moving {selectedNodes.length} class
        {selectedNodes.length > 1 ? "es" : ""}.
        {moveChildren && " All child classes will also be moved recursively."}
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button type="button" color="gray" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          color="blue"
          disabled={true}
          title="Move functionality is not yet available"
        >
          Move Classes (Not Available)
        </Button>
      </div>
    </form>
  );
}

/**
 * Concept Scheme Move Form
 *
 * Form for moving concept schemes to different taxonomy levels
 * @deprecated Move functionality is not yet supported by the backend
 */

import React, { useState } from "react";
import { Button, Label, Checkbox, Alert } from "flowbite-react";
import { Info } from "lucide-react";
import { ConceptScheme } from "@/api/types/ontology";
import { TaxonomySelector } from "@/components/node_selectors/taxonomy_selector";
import { useButterToast } from "@/hooks/useButterToast";

interface ConceptSchemeMoveFormProps {
  selectedNodes: ConceptScheme[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function ConceptSchemeMoveForm({
  selectedNodes,
  onSuccess,
  onCancel,
}: ConceptSchemeMoveFormProps) {
  const [targetParentId, setTargetParentId] = useState<string>("");
  const [moveChildren, setMoveChildren] = useState(true);
  const toast = useButterToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    toast.error("Move functionality is not yet implemented");
    onCancel();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Alert color="info" icon={Info}>
        <span className="font-medium">Move Concept Schemes</span>
        <p className="mt-1 text-sm">
          Moving concept schemes to a different taxonomy or changing their
          parent concept scheme.
        </p>
      </Alert>

      <div>
        <Label htmlFor="target-taxonomy">Target Taxonomy</Label>
        <TaxonomySelector
          value={targetParentId}
          onSelect={(taxonomy) => setTargetParentId(taxonomy?.id || "")}
          placeholder="Select target taxonomy"
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="move-children"
          checked={moveChildren}
          onChange={(e) => setMoveChildren(e.target.checked)}
        />
        <Label htmlFor="move-children" className="text-sm">
          Also move all child classes
        </Label>
      </div>

      <div className="text-sm text-gray-600">
        Moving {selectedNodes.length} concept scheme
        {selectedNodes.length > 1 ? "s" : ""}.
        {moveChildren && " All child classes will also be moved."}
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
          Move Concept Schemes (Not Available)
        </Button>
      </div>
    </form>
  );
}

/**
 * Attribute Panel Component
 *
 * Manages the complete attribute workflow: display, creation, editing, and deletion
 */

import React, { useState } from "react";
import { Spinner, Button, Alert } from "flowbite-react";
import { Plus, AlertCircle } from "lucide-react";
import type { OntologyClassAttribute } from "@/api/types/ontology";
import {
  useNodeAttributes,
  useNodeAttributeMutations,
} from "@/api/hooks/ontologyClasses/useNodeAttributes";
import { AttributeList } from "./AttributeList";
import { AttributeEditor } from "./AttributeEditor";
import { toast } from "@/utils/toast";

interface AttributePanelProps {
  nodeId: string;
}

export const AttributePanel: React.FC<AttributePanelProps> = ({ nodeId }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editingAttribute, setEditingAttribute] = useState<
    OntologyClassAttribute | undefined
  >();

  // Fetch resolved attributes
  const {
    data: attributes = [],
    isLoading: attributesLoading,
    error: attributesError,
    refetch: refetchAttributes,
  } = useNodeAttributes(nodeId);

  // Mutations for attribute operations
  const { setAttributesMutation, removeAttributeMutation } =
    useNodeAttributeMutations(nodeId);

  // Get existing keys for validation
  const existingKeys = attributes
    .filter((attr) => attr.key !== editingAttribute?.key) // Exclude current attribute being edited
    .map((attr) => attr.key);

  // Helper to convert ResolvedAttribute to OntologyClassAttribute
  const toOntologyClassAttribute = (
    attr: (typeof attributes)[number],
  ): OntologyClassAttribute => ({
    key: attr.key,
    title: attr.title,
    value_type: attr.value_type,
    value: attr.value,
  });

  // Handle attribute save (create or update)
  const handleSaveAttribute = async (attribute: OntologyClassAttribute) => {
    try {
      if (editingAttribute) {
        // For editing, we need to replace the entire attributes list
        // Remove the old key and add the new one
        const newAttributes = attributes
          .filter(
            (attr) => attr.key !== editingAttribute.key && !attr.inherited,
          )
          .map(toOntologyClassAttribute)
          .concat(attribute);

        await setAttributesMutation.mutateAsync(newAttributes);
        toast.success("Attribute updated successfully");
      } else {
        // For creating, add to existing local attributes
        const localAttributes = attributes
          .filter((attr) => !attr.inherited)
          .map(toOntologyClassAttribute);
        const newAttributes = localAttributes.concat(attribute);

        await setAttributesMutation.mutateAsync(newAttributes);
        toast.success("Attribute created successfully");
      }

      setIsEditing(false);
      setEditingAttribute(undefined);
      await refetchAttributes();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to save attribute";
      toast.error(message);
      throw error; // Re-throw for form error display
    }
  };

  // Handle attribute removal
  const handleRemoveAttribute = async (key: string) => {
    try {
      await removeAttributeMutation.mutateAsync(key);
      toast.success("Attribute removed successfully");
      await refetchAttributes();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to remove attribute";
      toast.error(message);
    }
  };

  // Handle edit button click
  const handleEditAttribute = (attribute: OntologyClassAttribute) => {
    setEditingAttribute(attribute);
    setIsEditing(true);
  };

  // Handle cancel
  const handleCancel = () => {
    setIsEditing(false);
    setEditingAttribute(undefined);
  };

  if (attributesError) {
    return (
      <Alert color="failure" icon={AlertCircle}>
        <span className="font-medium">Error loading attributes</span>
        <div className="text-sm">{String(attributesError)}</div>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Attributes</h2>
        {!isEditing && (
          <Button
            size="sm"
            color="blue"
            onClick={() => {
              setEditingAttribute(undefined);
              setIsEditing(true);
            }}
            disabled={attributesLoading}
          >
            <Plus className="mr-1 h-4 w-4" />
            Add Attribute
          </Button>
        )}
      </div>

      {isEditing ? (
        <AttributeEditor
          onSave={handleSaveAttribute}
          isLoading={setAttributesMutation.isPending}
          initialAttribute={editingAttribute}
          onCancel={handleCancel}
          existingKeys={existingKeys}
        />
      ) : attributesLoading ? (
        <div className="flex items-center justify-center py-8">
          <Spinner size="lg" />
          <span className="ml-2">Loading attributes...</span>
        </div>
      ) : (
        <AttributeList
          attributes={attributes}
          onRemoveAttribute={handleRemoveAttribute}
          onEditAttribute={handleEditAttribute}
          isLoading={removeAttributeMutation.isPending}
        />
      )}
    </div>
  );
};

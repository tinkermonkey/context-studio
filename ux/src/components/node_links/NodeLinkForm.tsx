/**
 * NodeLinkForm Component
 *
 * Inline form for creating new node links
 */

import React, { useState } from "react";
import { useForm } from "@tanstack/react-form";
import { Button, Alert, Label, Radio } from "flowbite-react";
import { Info, ArrowRight } from "lucide-react";

import {
  OntologyClass,
  OntologyClassLink,
  OntologyClassLinkCreate,
} from "@/api/types/ontologyClasss";
import { useCreateNodeLink } from "@/api/hooks/relationships/useNodeLinkMutations";
import { PredicateSelector } from "@/components/node_selectors/predicate_selector";
import { OntologyClassSelector } from "@/components/node_selectors/ontologyClass_selector";
import { toast } from "@/utils/toast";

interface NodeLinkFormProps {
  currentNode: OntologyClass;
  existingLinks: OntologyClassLink[];
  onSuccess: () => void;
  onCancel: () => void;
}

type Direction = "outgoing" | "incoming";

export const NodeLinkForm: React.FC<NodeLinkFormProps> = ({
  currentNode,
  existingLinks,
  onSuccess,
  onCancel,
}) => {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [direction, setDirection] = useState<Direction>("outgoing");

  const createLinkMutation = useCreateNodeLink({
    onSuccess: () => {
      toast.success("Link created successfully");
      onSuccess();
    },
    onError: (error: Error) => {
      const message =
        error instanceof Error ? error.message : "Failed to create link";
      toast.error(message);
    },
  });

  const form = useForm({
    defaultValues: {
      targetNodeId: "",
      predicateId: "",
      predicate: "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);

      // Validation
      if (!value.predicateId) {
        setSubmitError("Predicate is required");
        return;
      }
      if (!value.targetNodeId) {
        setSubmitError("Target node is required");
        return;
      }

      // Check for duplicate
      const isDuplicate = existingLinks.some((link) => {
        if (direction === "outgoing") {
          return (
            link.source_node_id === currentNode.id &&
            link.target_node_id === value.targetNodeId &&
            (link.predicate === value.predicate ||
              link.predicate_id === value.predicateId)
          );
        } else {
          return (
            link.source_node_id === value.targetNodeId &&
            link.target_node_id === currentNode.id &&
            (link.predicate === value.predicate ||
              link.predicate_id === value.predicateId)
          );
        }
      });

      if (isDuplicate) {
        setSubmitError("This link already exists");
        return;
      }

      try {
        const linkData: OntologyClassLinkCreate = {
          source_node_id:
            direction === "outgoing" ? currentNode.id : value.targetNodeId,
          target_node_id:
            direction === "outgoing" ? value.targetNodeId : currentNode.id,
          predicate: value.predicate,
          predicate_id: value.predicateId,
        };

        await createLinkMutation.mutateAsync(linkData);
      } catch (
         
        error: any
      ) {
        let message = "An error occurred";
        const detail =
          error?.response?.data?.detail ||
          error?.data?.detail ||
          error?.body?.detail ||
          error?.detail;

        if (Array.isArray(detail)) {
           
          message = detail.map((d: any) => d.msg).join("; ");
        } else if (error?.message) {
          message = error.message;
        } else if (typeof error === "string") {
          message = error;
        }
        setSubmitError(message);
        console.error("Failed to create link:", error);
      }
    },
  });

  return (
    <div className="space-y-4 rounded-lg border bg-gray-50 p-4">
      {/* Context Info */}
      <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
        <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
          <Info className="h-4 w-4" />
          <span>
            Creating link for: <strong>{currentNode.title}</strong> (
            {currentNode.node_type})
          </span>
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          form.handleSubmit();
        }}
        className="space-y-4"
      >
        {/* Direction */}
        <div>
          <Label className="mb-2 block font-medium">Direction *</Label>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Radio
                id="direction-outgoing"
                name="direction"
                value="outgoing"
                checked={direction === "outgoing"}
                onChange={() => setDirection("outgoing")}
              />
              <Label
                htmlFor="direction-outgoing"
                className="flex items-center gap-2"
              >
                <span>{currentNode.title}</span>
                <ArrowRight className="h-4 w-4" />
                <span>Target</span>
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Radio
                id="direction-incoming"
                name="direction"
                value="incoming"
                checked={direction === "incoming"}
                onChange={() => setDirection("incoming")}
              />
              <Label
                htmlFor="direction-incoming"
                className="flex items-center gap-2"
              >
                <span>Target</span>
                <ArrowRight className="h-4 w-4" />
                <span>{currentNode.title}</span>
              </Label>
            </div>
          </div>
        </div>

        {/* Predicate */}
        <form.Field name="predicateId">
          {(field) => (
            <div>
              <Label
                htmlFor="link-predicate"
                className="mb-1 block font-medium"
              >
                Predicate *
              </Label>
              <PredicateSelector
                value={field.state.value}
                onSelect={(predicate) => {
                  field.handleChange(predicate?.id || "");
                  form.setFieldValue("predicate", predicate?.title || "");
                }}
                placeholder="Select predicate..."
              />
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors[0]}
                </div>
              )}
            </div>
          )}
        </form.Field>

        {/* Target Node */}
        <form.Field name="targetNodeId">
          {(field) => (
            <div>
              <Label htmlFor="link-target" className="mb-1 block font-medium">
                Target Node *
              </Label>
              <OntologyClassSelector
                value={field.state.value}
                onSelect={(node) => field.handleChange(node?.id || "")}
                excludeNodeIds={[currentNode.id]}
                placeholder="Select target node..."
              />
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors[0]}
                </div>
              )}
            </div>
          )}
        </form.Field>

        {/* Error Alert */}
        {submitError && (
          <Alert color="failure" icon={Info}>
            {submitError}
          </Alert>
        )}

        {/* Action Buttons */}
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            color="gray"
            onClick={onCancel}
            disabled={createLinkMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={form.state.isSubmitting || createLinkMutation.isPending}
          >
            {form.state.isSubmitting || createLinkMutation.isPending
              ? "Creating..."
              : "Create Link"}
          </Button>
        </div>
      </form>
    </div>
  );
};

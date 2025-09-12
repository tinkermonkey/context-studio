/**
 * Predicate Form Component
 *
 * Form for creating and editing predicates
 */

import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info } from "lucide-react";
import type { PredicateCreate, PredicateOut } from "@/api/services/predicates";
import {
  useCreatePredicate,
  useUpdatePredicate,
} from "@/api/hooks/predicates/usePredicateMutations";

interface PredicateFormProps {
  onSuccess?: (predicate: PredicateOut) => void;
  predicate?: PredicateOut; // For edit mode
  // Future child form props
  mode?: "create" | "edit" | "child";
}

const PredicateForm: React.FC<PredicateFormProps> = ({
  onSuccess,
  predicate,
  mode = "create",
}) => {
  const createPredicateMutation = useCreatePredicate();
  const updatePredicateMutation = useUpdatePredicate();
  const isEdit = !!predicate;
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  // Auto-generate identifier from title
  const generateIdentifier = (title: string): string => {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
  };

  const form = useForm({
    defaultValues: {
      title: predicate?.title ?? "",
      definition: predicate?.definition ?? "",
      identifier: predicate?.identifier ?? "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        // Auto-generate identifier if not provided
        const submissionData = {
          ...value,
          identifier: value.identifier || generateIdentifier(value.title),
        };

        let result;
        if (isEdit && predicate?.id) {
          result = await updatePredicateMutation.mutateAsync({
            id: predicate.id,
            data: submissionData,
          });
        } else {
          result = await createPredicateMutation.mutateAsync(
            submissionData as PredicateCreate,
          );
        }
        if (onSuccess) onSuccess(result);
        form.reset();
      } catch (error: any) {
        let message = "An error occurred";
        // Log the full error for debugging
        console.error("Full error object:", error);
        console.error("Error detail:", error?.detail);

        // Try to find the detail array in various places
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
        } else {
          message = JSON.stringify(error);
        }
        setSubmitError(message);
        // TODO: Use useButterToast for error notification
        console.error(
          isEdit
            ? "Failed to update predicate:"
            : "Failed to create predicate:",
          error,
        );
      }
    },
  });

  return (
    <>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          form.handleSubmit();
        }}
        className="flex flex-col gap-4"
      >
        <form.Field
          name="title"
          validators={{
            onChange: ({ value }) => (!value ? "Title is required" : undefined),
          }}
        >
          {(field) => (
            <div>
              <Label
                htmlFor="predicate-title"
                className="mb-1 block font-medium"
              >
                Title
              </Label>
              <TextInput
                id="predicate-title"
                placeholder="Title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => {
                  field.handleChange(e.target.value);
                  // Auto-update identifier if it's empty or auto-generated
                  const currentIdentifier = form.getFieldValue("identifier");
                  if (
                    !currentIdentifier ||
                    currentIdentifier === generateIdentifier(field.state.value)
                  ) {
                    form.setFieldValue(
                      "identifier",
                      generateIdentifier(e.target.value),
                    );
                  }
                }}
                required
                autoFocus
              />
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors[0]}
                </div>
              )}
            </div>
          )}
        </form.Field>

        <form.Field name="definition">
          {(field) => (
            <div>
              <Label
                htmlFor="predicate-definition"
                className="mb-1 block font-medium"
              >
                Definition (optional)
              </Label>
              <Textarea
                id="predicate-definition"
                placeholder="Definition (optional)"
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                rows={3}
              />
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors[0]}
                </div>
              )}
            </div>
          )}
        </form.Field>

        <form.Field
          name="identifier"
          validators={{
            onChange: ({ value }) => {
              if (value && !/^[a-z0-9_]+$/i.test(value)) {
                return "Identifier can only contain letters, numbers, and underscores";
              }
              return undefined;
            },
          }}
        >
          {(field) => (
            <div>
              <Label
                htmlFor="predicate-identifier"
                className="mb-1 block font-medium"
              >
                Identifier (optional)
              </Label>
              <TextInput
                id="predicate-identifier"
                placeholder="Auto-generated from title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
              />
              <p className="mt-1 text-sm text-gray-500">
                Unique identifier for API usage. Auto-generated if not provided.
              </p>
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors[0]}
                </div>
              )}
            </div>
          )}
        </form.Field>

        {submitError && (
          <Alert color="failure" className="mb-2" icon={Info}>
            {submitError}
          </Alert>
        )}

        <div className="flex items-center justify-end gap-2">
          <Button
            type="submit"
            disabled={
              form.state.isSubmitting ||
              createPredicateMutation.isPending ||
              updatePredicateMutation.isPending
            }
          >
            {form.state.isSubmitting ||
            createPredicateMutation.isPending ||
            updatePredicateMutation.isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Predicate"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { PredicateForm };

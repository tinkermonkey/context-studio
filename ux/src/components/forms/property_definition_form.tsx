/**
 * Property Definition Form Component
 *
 * Form for creating and editing property definitions
 */

import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info } from "lucide-react";
import type {
  PropertyDefinitionCreate,
  PropertyDefinition,
} from "@/api/types/ontology";
import {
  useCreatePropertyDefinition,
  useUpdatePropertyDefinition,
} from "@/api/hooks/propertyDefinitions";

interface PropertyDefinitionFormProps {
  onSuccess?: (propertyDefinition: PropertyDefinition) => void;
  propertyDefinition?: PropertyDefinition;
  mode?: "create" | "edit" | "child";
}

const PropertyDefinitionForm: React.FC<PropertyDefinitionFormProps> = ({
  onSuccess,
  propertyDefinition,
}) => {
  const createPropertyDefinitionMutation = useCreatePropertyDefinition();
  const updatePropertyDefinitionMutation = useUpdatePropertyDefinition();
  const isEdit = !!propertyDefinition;
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const form = useForm({
    defaultValues: {
      identifier: propertyDefinition?.identifier ?? "",
      title: propertyDefinition?.title ?? "",
      description: propertyDefinition?.description ?? "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        const submissionData: PropertyDefinitionCreate = {
          identifier: value.identifier,
          title: value.title,
          description: value.description || null,
        };

        let result;
        if (isEdit && propertyDefinition?.id) {
          result = await updatePropertyDefinitionMutation.mutateAsync({
            id: propertyDefinition.id,
            data: submissionData,
          });
        } else {
          result =
            await createPropertyDefinitionMutation.mutateAsync(submissionData);
        }
        if (onSuccess) onSuccess(result);
        form.reset();
      } catch (error: any) {
        let message: string;
        console.error("Full error object:", error);
        console.error("Error detail:", error?.detail);

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
        console.error(
          isEdit
            ? "Failed to update property definition:"
            : "Failed to create property definition:",
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
          name="identifier"
          validators={{
            onChange: ({ value }) => (!value ? "Identifier is required" : undefined),
          }}
        >
          {(field) => (
            <div>
              <Label
                htmlFor="property-definition-identifier"
                className="mb-1 block font-medium"
              >
                Identifier
              </Label>
              <TextInput
                id="property-definition-identifier"
                data-testid="property-definition-identifier-input"
                placeholder="Identifier"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => {
                  field.handleChange(e.target.value);
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

        <form.Field
          name="title"
          validators={{
            onChange: ({ value }) => (!value ? "Title is required" : undefined),
          }}
        >
          {(field) => (
            <div>
              <Label
                htmlFor="property-definition-title"
                className="mb-1 block font-medium"
              >
                Title
              </Label>
              <TextInput
                id="property-definition-title"
                data-testid="property-definition-title-input"
                placeholder="Title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => {
                  field.handleChange(e.target.value);
                }}
                required
              />
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors[0]}
                </div>
              )}
            </div>
          )}
        </form.Field>

        <form.Field name="description">
          {(field) => (
            <div>
              <Label
                htmlFor="property-definition-description"
                className="mb-1 block font-medium"
              >
                Description (optional)
              </Label>
              <Textarea
                id="property-definition-description"
                data-testid="property-definition-description-input"
                placeholder="Description (optional)"
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

        {submitError && (
          <Alert color="failure" className="mb-2" icon={Info}>
            {submitError}
          </Alert>
        )}

        <div className="flex items-center justify-end gap-2">
          <Button
            type="submit"
            data-testid="property-definition-submit-button"
            disabled={
              form.state.isSubmitting ||
              createPropertyDefinitionMutation.isPending ||
              updatePropertyDefinitionMutation.isPending
            }
          >
            {form.state.isSubmitting ||
            createPropertyDefinitionMutation.isPending ||
            updatePropertyDefinitionMutation.isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Property Definition"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { PropertyDefinitionForm };

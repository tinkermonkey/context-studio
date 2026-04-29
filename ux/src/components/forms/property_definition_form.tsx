/**
 * Property Definition Form Component
 *
 * Form for creating and editing property definitions
 */

import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info } from "lucide-react";
import type { PropertyDefinitionCreate, PropertyDefinitionOut } from "@/api/services/propertyDefinitions";
import {
  useCreatePropertyDefinition,
  useUpdatePropertyDefinition,
} from "@/api/hooks/propertyDefinitions";

interface PropertyDefinitionFormProps {
  onSuccess?: (propertyDefinition: PropertyDefinitionOut) => void;
  propertyDefinition?: PropertyDefinitionOut;
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

  const identifierManuallyEdited = React.useRef(false);
  const lastAutoIdentifier = React.useRef("");
  const [titleValue, setTitleValue] = React.useState(propertyDefinition?.title ?? "");

  const generateIdentifier = (title: string): string => {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
  };

  const form = useForm({
    defaultValues: {
      title: propertyDefinition?.title ?? "",
      definition: propertyDefinition?.definition ?? "",
      identifier: propertyDefinition?.identifier ?? "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        const submissionData = {
          ...value,
          identifier: value.identifier || generateIdentifier(value.title),
        };

        let result;
        if (isEdit && propertyDefinition?.id) {
          result = await updatePropertyDefinitionMutation.mutateAsync({
            id: propertyDefinition.id,
            data: submissionData,
          });
        } else {
          result = await createPropertyDefinitionMutation.mutateAsync(
            submissionData as PropertyDefinitionCreate,
          );
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
          message = detail
            .map((d: any) => d.msg)
            .join("; ");
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

  React.useEffect(() => {
    if (identifierManuallyEdited.current) {
      return;
    }

    const timeoutId = setTimeout(() => {
      const newIdentifier = generateIdentifier(titleValue);
      const currentIdentifier = form.getFieldValue("identifier");

      if (newIdentifier !== currentIdentifier) {
        form.setFieldValue("identifier", newIdentifier);
        lastAutoIdentifier.current = newIdentifier;
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [titleValue]);

  React.useEffect(() => {
    if (propertyDefinition?.identifier) {
      identifierManuallyEdited.current = true;
      lastAutoIdentifier.current = propertyDefinition.identifier;
    }
  }, [propertyDefinition?.identifier]);

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
                  setTitleValue(e.target.value);
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
                htmlFor="property-definition-definition"
                className="mb-1 block font-medium"
              >
                Definition (optional)
              </Label>
              <Textarea
                id="property-definition-definition"
                data-testid="property-definition-definition-input"
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
                htmlFor="property-definition-identifier"
                className="mb-1 block font-medium"
              >
                Identifier (optional)
              </Label>
              <TextInput
                id="property-definition-identifier"
                data-testid="property-definition-identifier-input"
                placeholder="Auto-generated from title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => {
                  field.handleChange(e.target.value);
                  const title = form.getFieldValue("title");
                  const autoGenerated = generateIdentifier(title);
                  if (e.target.value !== autoGenerated) {
                    identifierManuallyEdited.current = true;
                  } else {
                    identifierManuallyEdited.current = false;
                  }
                }}
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

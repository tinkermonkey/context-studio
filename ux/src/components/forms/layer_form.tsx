import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info } from "lucide-react";
import type { OntologyClass } from "@/api/types/ontology";
import { useCreateTaxonomy } from "@/api/hooks/taxonomies/useTaxonomies";
import { useUpdateTaxonomy } from "@/api/hooks/taxonomies/useTaxonomies";

interface LayerFormProps {
  onSuccess?: (layer: OntologyClass) => void;
  layer?: OntologyClass;
}

const LayerForm: React.FC<LayerFormProps> = ({ onSuccess, layer }) => {
  const createLayerMutation = useCreateTaxonomy();
  const updateLayerMutation = useUpdateTaxonomy();
  const isEdit = !!layer;
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const form = useForm({
    defaultValues: {
      title: layer?.title ?? "",
      definition: layer?.definition ?? "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        let result;
        if (isEdit && layer?.id) {
          result = await updateLayerMutation.mutateAsync({
            id: layer.id,
            data: {
              title: value.title,
              description: value.definition,
            },
          });
        } else {
          result = await createLayerMutation.mutateAsync({
            title: value.title,
            description: value.definition,
          });
        }
        if (onSuccess) onSuccess(result);
        form.reset();
      } catch (
        error: any  
      ) {
        let message: string;
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
          message = detail
            .map(
               
              (d: any) => d.msg,
            )
            .join("; ");
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
          isEdit ? "Failed to update layer:" : "Failed to create layer:",
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
        data-testid="layer-form"
      >
        <form.Field
          name="title"
          validators={{
            onChange: ({ value }) => (!value ? "Title is required" : undefined),
          }}
        >
          {(field) => (
            <div>
              <Label htmlFor="layer-title" className="mb-1 block font-medium">
                Title
              </Label>
              <TextInput
                id="layer-title"
                placeholder="Title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                autoFocus
                data-testid="layer-title-input"
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
                htmlFor="layer-definition"
                className="mb-1 block font-medium"
              >
                Definition (optional)
              </Label>
              <Textarea
                id="layer-definition"
                placeholder="Definition (optional)"
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                data-testid="layer-definition-input"
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
            disabled={
              form.state.isSubmitting ||
              createLayerMutation.isPending ||
              updateLayerMutation.isPending
            }
            data-testid="layer-submit-button"
          >
            {form.state.isSubmitting ||
            createLayerMutation.isPending ||
            updateLayerMutation.isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Layer"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { LayerForm };

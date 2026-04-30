import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info } from "lucide-react";
import type { Taxonomy } from "@/api/types/ontology";
import { useCreateTaxonomy, useUpdateTaxonomy } from "@/api/hooks/taxonomies";

interface TaxonomyFormProps {
  onSuccess?: (taxonomy: Taxonomy) => void;
  taxonomy?: Taxonomy;
}

const TaxonomyForm: React.FC<TaxonomyFormProps> = ({ onSuccess, taxonomy }) => {
  const createTaxonomyMutation = useCreateTaxonomy();
  const updateTaxonomyMutation = useUpdateTaxonomy();
  const isEdit = !!taxonomy;
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const form = useForm({
    defaultValues: {
      title: taxonomy?.title ?? "",
      description: taxonomy?.description ?? "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        let result;
        if (isEdit && taxonomy?.id) {
          result = await updateTaxonomyMutation.mutateAsync({
            id: taxonomy.id,
            data: value,
          });
        } else {
          result = await createTaxonomyMutation.mutateAsync({
            title: value.title,
            description: value.description,
          });
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
          isEdit ? "Failed to update taxonomy:" : "Failed to create taxonomy:",
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
        data-testid="taxonomy-form"
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
                htmlFor="taxonomy-title"
                className="mb-1 block font-medium"
              >
                Title
              </Label>
              <TextInput
                id="taxonomy-title"
                placeholder="Title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                autoFocus
                data-testid="taxonomy-title-input"
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
                htmlFor="taxonomy-description"
                className="mb-1 block font-medium"
              >
                Description (optional)
              </Label>
              <Textarea
                id="taxonomy-description"
                placeholder="Description (optional)"
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                data-testid="taxonomy-description-input"
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
              createTaxonomyMutation.isPending ||
              updateTaxonomyMutation.isPending
            }
            data-testid="taxonomy-submit-button"
          >
            {form.state.isSubmitting ||
            createTaxonomyMutation.isPending ||
            updateTaxonomyMutation.isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Taxonomy"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { TaxonomyForm };

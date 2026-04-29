import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info, Database } from "lucide-react";
import type { OntologyClass } from "@/api/types/ontology";
import { useCreateConceptScheme, useUpdateConceptScheme } from "@/api/hooks/conceptSchemes";
import { TaxonomySelector } from "@/components/node_selectors/taxonomy_selector";
import { PropertySelector } from "@/components/node_selectors/property_selector";

interface ConceptSchemeFormProps {
  onSuccess?: (conceptScheme: OntologyClass) => void;
  conceptScheme?: OntologyClass;
  parentTaxonomyId?: string;
  parentTaxonomy?: OntologyClass;
  mode?: "create" | "edit" | "child";
}

const ConceptSchemeForm: React.FC<ConceptSchemeFormProps> = ({
  onSuccess,
  conceptScheme,
  parentTaxonomyId,
  parentTaxonomy,
  mode = "create",
}) => {
  const createConceptSchemeMutation = useCreateConceptScheme();
  const updateConceptSchemeMutation = useUpdateConceptScheme();
  const isEdit = !!conceptScheme;
  const isChildMode = mode === "child" || !!parentTaxonomyId;
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const getDefaultValues = () => ({
    title: conceptScheme?.title ?? "",
    definition: conceptScheme?.definition ?? "",
    parent_node_id: conceptScheme?.parent_node_id ?? parentTaxonomyId ?? "",
    structural_predicate_id: conceptScheme?.structural_predicate_id ?? undefined,
  });

  const form = useForm({
    defaultValues: getDefaultValues(),
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        let result;
        if (isEdit && conceptScheme?.id) {
          result = await updateConceptSchemeMutation.mutateAsync({
            id: conceptScheme.id,
            data: value,
          });
        } else {
          const createData: any = {
            title: value.title,
            definition: value.definition,
          };

          if (value.structural_predicate_id) {
            createData.structural_predicate_id = value.structural_predicate_id;
          }

          result = await createConceptSchemeMutation.mutateAsync({
            taxonomyId: value.parent_node_id,
            data: createData,
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
          isEdit ? "Failed to update concept scheme:" : "Failed to create concept scheme:",
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
        {isChildMode && parentTaxonomy && (
          <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
              <Info className="h-4 w-4" />
              <span>Creating concept scheme in taxonomy:</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <Database className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              <span className="font-semibold text-blue-900 dark:text-blue-100">
                {parentTaxonomy.title}
              </span>
            </div>
          </div>
        )}

        <form.Field
          name="title"
          validators={{
            onChange: ({ value }) => (!value ? "Title is required" : undefined),
          }}
        >
          {(field) => (
            <div>
              <Label htmlFor="concept-scheme-title" className="mb-1 block font-medium">
                Title
              </Label>
              <TextInput
                id="concept-scheme-title"
                placeholder="Title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                autoFocus
                data-testid="concept-scheme-title-input"
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
                htmlFor="concept-scheme-definition"
                className="mb-1 block font-medium"
              >
                Definition
              </Label>
              <Textarea
                id="concept-scheme-definition"
                placeholder="Definition"
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                data-testid="concept-scheme-definition-input"
              />
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors[0]}
                </div>
              )}
            </div>
          )}
        </form.Field>

        {!isChildMode && (
          <form.Field
            name="parent_node_id"
            validators={{
              onChange: ({ value }) =>
                !value ? "Taxonomy is required" : undefined,
            }}
          >
            {(field) => (
              <div>
                <Label
                  htmlFor="concept-scheme-taxonomy"
                  className="mb-1 block font-medium"
                >
                  Taxonomy
                </Label>
                <TaxonomySelector
                  value={field.state.value}
                  onSelect={(taxonomy) => field.handleChange(taxonomy?.id || "")}
                  data-testid="concept-scheme-taxonomy-selector"
                />
                {field.state.meta.errors.length > 0 && (
                  <div className="mt-1 text-sm text-red-600">
                    {field.state.meta.errors[0]}
                  </div>
                )}
              </div>
            )}
          </form.Field>
        )}

        <form.Field name="structural_predicate_id">
          {(field) => (
            <div>
              <Label
                htmlFor="concept-scheme-property"
                className="mb-1 block font-medium"
              >
                Structural Property (optional)
              </Label>
              <PropertySelector
                value={field.state.value}
                onSelect={(property) => {
                  const propertyId = property?.id || undefined;
                  field.handleChange(propertyId);
                }}
              />
              <p className="mt-1 text-sm text-gray-500">
                The property that defines this concept scheme's core hierarchical relationships
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
              createConceptSchemeMutation.isPending ||
              updateConceptSchemeMutation.isPending
            }
            data-testid="concept-scheme-submit-button"
          >
            {form.state.isSubmitting ||
            createConceptSchemeMutation.isPending ||
            updateConceptSchemeMutation.isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Concept Scheme"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { ConceptSchemeForm };

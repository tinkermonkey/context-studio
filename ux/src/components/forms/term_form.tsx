import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info, Database, Hash } from "lucide-react";
import type { OntologyClass } from "@/api/types/ontology";
import { useCreateOntologyClass } from "@/api/hooks/ontologyClasses/useOntologyClasses";
import { useUpdateOntologyClass } from "@/api/hooks/ontologyClasses/useOntologyClasses";
import { DomainSelector } from "@/components/node_selectors/domain_selector";

interface TermFormProps {
  onSuccess?: (term: OntologyClass) => void;
  term?: OntologyClass; // For edit mode
  // Child form props
  parentDomainId?: string;
  parentDomain?: OntologyClass;
  parentTermId?: string;
  parentTerm?: OntologyClass;
  mode?: "create" | "edit" | "child";
}

const TermForm: React.FC<TermFormProps> = ({
  onSuccess,
  term,
  parentDomainId,
  parentDomain,
  parentTermId,
  parentTerm,
  mode = "create",
}) => {
  const createTermMutation = useCreateOntologyClass();
  const updateTermMutation = useUpdateOntologyClass();
  const isEdit = !!term;
  const isChildMode = mode === "child" || !!parentDomainId || !!parentTermId;
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const getDefaultValues = () => ({
    title: term?.title ?? "",
    description: term?.description ?? "",
    parent_class_id:
      term?.parent_class_id ?? parentDomainId ?? parentTermId ?? "",
  });

  const form = useForm({
    defaultValues: getDefaultValues(),
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        let result;
        if (isEdit && term?.id) {
          result = await updateTermMutation.mutateAsync({
            id: term.id,
            data: {
              title: value.title,
              description: value.description,
            },
          });
        } else {
          // For creating, we need the schemeId, which should be parentDomainId
          const schemeId = parentDomainId || value.parent_class_id;
          result = await createTermMutation.mutateAsync({
            schemeId: schemeId,
            data: {
              title: value.title,
              description: value.description,
              parent_class_id: parentTermId || undefined,
            },
          });
        }
        if (onSuccess) onSuccess(result);
        form.reset();

         
      } catch (error: any) {
        // Log the full error for debugging
        console.error("Full error object:", error);
        console.error("Error detail:", error?.detail);

        // Try to find the detail array in various places
        const detail =
          error?.response?.data?.detail ||
          error?.data?.detail ||
          error?.body?.detail ||
          error?.detail;

        let message: string;
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
          isEdit ? "Failed to update term:" : "Failed to create term:",
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
        {/* Parent Context Display */}
        {isChildMode && (parentDomain || parentTerm) && (
          <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
              <Info className="h-4 w-4" />
              <span>
                Creating term in {parentDomain ? "domain" : "parent term"}:
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              {parentDomain ? (
                <Database className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              ) : (
                <Hash className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              )}
              <span className="font-semibold text-blue-900 dark:text-blue-100">
                {parentDomain?.title || parentTerm?.title}
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
              <Label htmlFor="term-title" className="mb-1 block font-medium">
                Title
              </Label>
              <TextInput
                id="term-title"
                placeholder="Title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                autoFocus
                data-testid="term-title-input"
              />
            </div>
          )}
        </form.Field>
        <form.Field
          name="description"
          validators={{
            onChange: ({ value }) =>
              !value ? "Description is required" : undefined,
          }}
        >
          {(field) => (
            <div>
              <Label
                htmlFor="term-description"
                className="mb-1 block font-medium"
              >
                Description
              </Label>
              <Textarea
                id="term-description"
                placeholder="Description"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                data-testid="term-description-input"
              />
            </div>
          )}
        </form.Field>

        {/* Hide domain selector in child mode when parent is provided */}
        {!isChildMode && (
          <form.Field
            name="parent_class_id"
            validators={{
              onChange: ({ value }) =>
                !value ? "Parent is required" : undefined,
            }}
          >
            {(field) => {
              return (
                <div>
                  <Label
                    htmlFor="term-parent"
                    className="mb-1 block font-medium"
                  >
                    Parent (Domain or Term)
                  </Label>
                  <DomainSelector
                    value={field.state.value}
                    onSelect={(domain) => {
                      field.handleChange(domain?.id || "");
                    }}
                    data-testid="term-domain-selector"
                  />
                  {field.state.meta.errors.length > 0 && (
                    <div className="mt-1 text-sm text-red-600">
                      {field.state.meta.errors[0]}
                    </div>
                  )}
                </div>
              );
            }}
          </form.Field>
        )}

        {/* Parent selection is now unified under parent_node_id */}

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
              createTermMutation.isPending ||
              updateTermMutation.isPending
            }
            data-testid="term-submit-button"
          >
            {form.state.isSubmitting ||
            createTermMutation.isPending ||
            updateTermMutation.isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Term"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { TermForm };

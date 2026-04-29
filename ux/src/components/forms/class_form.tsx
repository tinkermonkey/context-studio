import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info, Database, Hash } from "lucide-react";
import type { OntologyClass, OntologyClassCreate } from "@/api/types/ontology";
import {
  useCreateOntologyClass,
  useUpdateOntologyClass,
} from "@/api/hooks/ontologyClasses";
import { ConceptSchemeSelector } from "@/components/node_selectors/concept_scheme_selector";

interface ClassFormProps {
  onSuccess?: (ontologyClass: OntologyClass) => void;
  ontologyClass?: OntologyClass;
  parentConceptSchemeId?: string;
  parentClassId?: string;
  mode?: "create" | "edit" | "child";
}

const ClassForm: React.FC<ClassFormProps> = ({
  onSuccess,
  ontologyClass,
  parentConceptSchemeId,
  parentClassId,
  mode = "create",
}) => {
  const createClassMutation = useCreateOntologyClass();
  const updateClassMutation = useUpdateOntologyClass();
  const isEdit = !!ontologyClass;
  const isChildMode =
    mode === "child" || !!parentConceptSchemeId || !!parentClassId;
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const getDefaultValues = () => ({
    title: ontologyClass?.title ?? "",
    definition: ontologyClass?.definition ?? "",
    parent_class_id: ontologyClass?.parent_class_id ?? parentClassId ?? "",
  });

  const form = useForm({
    defaultValues: getDefaultValues(),
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        const classData: OntologyClassCreate = {
          title: value.title,
          definition: value.definition || null,
          parent_class_id: value.parent_class_id || null,
        };

        let result;
        if (isEdit && ontologyClass?.id) {
          result = await updateClassMutation.mutateAsync({
            id: ontologyClass.id,
            data: classData,
          });
        } else {
          result = await createClassMutation.mutateAsync({
            schemeId: parentConceptSchemeId || "",
            data: classData,
          });
        }
        if (onSuccess) onSuccess(result);
        form.reset();
      } catch (error: any) {
        console.error("Full error object:", error);
        console.error("Error detail:", error?.detail);

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
        console.error(
          isEdit ? "Failed to update class:" : "Failed to create class:",
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
        {isChildMode && (parentConceptSchemeId || parentClassId) && (
          <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
              <Info className="h-4 w-4" />
              <span>
                Creating class in{" "}
                {parentConceptSchemeId ? "concept scheme" : "parent class"}
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              {parentConceptSchemeId ? (
                <Database className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              ) : (
                <Hash className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              )}
              <span className="font-semibold text-blue-900 dark:text-blue-100">
                {parentConceptSchemeId || parentClassId}
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
              <Label htmlFor="class-title" className="mb-1 block font-medium">
                Title
              </Label>
              <TextInput
                id="class-title"
                placeholder="Title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                autoFocus
                data-testid="class-title-input"
              />
            </div>
          )}
        </form.Field>
        <form.Field
          name="definition"
          validators={{
            onChange: ({ value }) =>
              !value ? "Definition is required" : undefined,
          }}
        >
          {(field) => (
            <div>
              <Label
                htmlFor="class-definition"
                className="mb-1 block font-medium"
              >
                Definition
              </Label>
              <Textarea
                id="class-definition"
                placeholder="Definition"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                data-testid="class-definition-input"
              />
            </div>
          )}
        </form.Field>

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
                    htmlFor="class-parent"
                    className="mb-1 block font-medium"
                  >
                    Parent (Concept Scheme or Class)
                  </Label>
                  <ConceptSchemeSelector
                    value={field.state.value}
                    onSelect={(conceptScheme) => {
                      field.handleChange(conceptScheme?.id || "");
                    }}
                    data-testid="class-concept-scheme-selector"
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
              createClassMutation.isPending ||
              updateClassMutation.isPending
            }
            data-testid="class-submit-button"
          >
            {form.state.isSubmitting ||
            createClassMutation.isPending ||
            updateClassMutation.isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Class"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { ClassForm };

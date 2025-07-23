import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info } from "lucide-react";
import type { TermCreate, TermOut } from "@/api/services/terms";
import {
  useCreateTerm,
  useUpdateTerm,
} from "@/api/hooks/terms/useTermMutations";
import { LayerSelector } from "@/components/node_selectors/layer_selector";
import { DomainSelector } from "@/components/node_selectors/domain_selector";
import { TermSelector } from "@/components/node_selectors/term_selector";

interface TermFormProps {
  onSuccess?: (term: any) => void;
  term?: TermOut;
}

const TermForm: React.FC<TermFormProps> = ({ onSuccess, term }) => {
  const createTermMutation = useCreateTerm();
  const updateTermMutation = useUpdateTerm();
  const isEdit = !!term;
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const form = useForm({
    defaultValues: {
      title: term?.title ?? "",
      definition: term?.definition ?? "",
      domain_id: term?.domain_id ?? "",
      layer_id: term?.layer_id ?? "",
      parent_term_id: term?.parent_term_id ?? "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        let result;
        if (isEdit && term?.id) {
          result = await updateTermMutation.mutateAsync({
            id: term.id,
            data: value,
          });
        } else {
          result = await createTermMutation.mutateAsync(value as TermCreate);
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
                htmlFor="term-definition"
                className="mb-1 block font-medium"
              >
                Definition
              </Label>
              <Textarea
                id="term-definition"
                placeholder="Definition"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
              />
            </div>
          )}
        </form.Field>
        <form.Field
          name="domain_id"
          validators={{
            onChange: ({ value }) =>
              !value ? "Domain is required" : undefined,
          }}
        >
          {(field) => {
            return (
              <div>
                <Label htmlFor="term-domain" className="mb-1 block font-medium">
                  Domain
                </Label>
                <DomainSelector
                  value={field.state.value}
                  onSelect={(domain) => {
                    field.handleChange(domain?.id || "");
                    // Set layer_id to the selected domain's layer_id
                    field.form.setFieldValue("layer_id", domain?.layer_id || "");
                  }}
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
        {/* layer_id is now hidden and set automatically from the selected domain */}
        <form.Field name="parent_term_id">
          {(field) => (
            <div>
              <Label
                htmlFor="term-parent-term"
                className="mb-1 block font-medium"
              >
                Parent Term (optional)
              </Label>
              <TermSelector
                value={field.state.value}
                onSelect={(term) => field.handleChange(term?.id || "")}
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
        <div className="flex items-center gap-2">
          <Button
            type="submit"
            disabled={
              form.state.isSubmitting ||
              createTermMutation.isPending ||
              updateTermMutation.isPending
            }
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

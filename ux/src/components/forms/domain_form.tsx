import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info } from "lucide-react";
import type { DomainCreate, DomainOut } from "@/api/services/domains";
import {
  useCreateDomain,
  useUpdateDomain,
} from "@/api/hooks/domains/useDomainMutations";
import { LayerSelector } from "@/components/node_selectors/layer_selector";

interface DomainFormProps {
  onSuccess?: (domain: any) => void;
  domain?: DomainOut;
}

const DomainForm: React.FC<DomainFormProps> = ({ onSuccess, domain }) => {
  const createDomainMutation = useCreateDomain();
  const updateDomainMutation = useUpdateDomain();
  const isEdit = !!domain;
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const form = useForm({
    defaultValues: {
      title: domain?.title ?? "",
      definition: domain?.definition ?? "",
      layer_id: domain?.layer_id ?? "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        let result;
        if (isEdit && domain?.id) {
          result = await updateDomainMutation.mutateAsync({
            id: domain.id,
            data: value,
          });
        } else {
          result = await createDomainMutation.mutateAsync(
            value as DomainCreate,
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
          isEdit ? "Failed to update domain:" : "Failed to create domain:",
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
              <Label htmlFor="domain-title" className="mb-1 block font-medium">
                Title
              </Label>
              <TextInput
                id="domain-title"
                placeholder="Title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
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
                htmlFor="domain-definition"
                className="mb-1 block font-medium"
              >
                Definition
              </Label>
              <Textarea
                id="domain-definition"
                placeholder="Definition"
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
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
          name="layer_id"
          validators={{
            onChange: ({ value }) => (!value ? "Layer is required" : undefined),
          }}
        >
          {(field) => (
            <div>
              <Label htmlFor="domain-layer" className="mb-1 block font-medium">
                Layer
              </Label>
              <LayerSelector
                value={field.state.value}
                onSelect={(layer) => field.handleChange(layer?.id || "")}
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
        <div className="flex justify-end items-center gap-2">
          <Button
            type="submit"
            disabled={
              form.state.isSubmitting ||
              createDomainMutation.isPending ||
              updateDomainMutation.isPending
            }
          >
            {form.state.isSubmitting ||
            createDomainMutation.isPending ||
            updateDomainMutation.isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Domain"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { DomainForm };

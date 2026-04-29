import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Button, Alert, Label } from "flowbite-react";
import { Info } from "lucide-react";
import type { CreateDatasetRequest } from "@/api/services/datasets";
import { useCreateDataset } from "@/api/hooks/datasets/useDatasetMutations";

interface DatasetFormProps {
  onSuccess?: (dataset: any) => void;  
}

const DatasetForm: React.FC<DatasetFormProps> = ({ onSuccess }) => {
  const createDatasetMutation = useCreateDataset();
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const form = useForm({
    defaultValues: {
      title: "",
      filename: "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        const result = await createDatasetMutation.mutateAsync(
          value as CreateDatasetRequest,
        );
        if (onSuccess) onSuccess(result);
        form.reset();
      } catch (
        error: any  
      ) {
        let message = "An error occurred";
        console.error("Full error object:", error);
        console.error("Error detail:", error?.detail);

        if (error?.response?.data?.detail) {
          if (Array.isArray(error.response.data.detail)) {
            // Validation errors from FastAPI
            const validationErrors = error.response.data.detail
              .map(
                 
                (err: any) => `${err.loc?.join(" > ")}: ${err.msg}`,
              )
              .join(", ");
            message = `Validation error: ${validationErrors}`;
          } else if (typeof error.response.data.detail === "string") {
            message = error.response.data.detail;
          }
        } else if (error?.message) {
          message = error.message;
        }
        setSubmitError(message);
      }
    },
  });

  const isSubmitting = createDatasetMutation.isPending;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      <div className="space-y-4">
        {submitError && (
          <Alert color="failure" icon={Info}>
            {submitError}
          </Alert>
        )}

        <form.Field
          name="title"
          validators={{
            onChange: ({ value }) =>
              !value ? "Dataset title is required" : undefined,
          }}
        >
          {(field) => (
            <div>
              <Label htmlFor="dataset-title" className="mb-1 block font-medium">
                Dataset Title
              </Label>
              <TextInput
                id="dataset-title"
                name={field.name}
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                placeholder="Enter dataset title"
                color={
                  field.state.meta.errors.length > 0 ? "failure" : undefined
                }
              />
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors.join(", ")}
                </div>
              )}
            </div>
          )}
        </form.Field>

        <form.Field
          name="filename"
          validators={{
            onChange: ({ value }) => {
              if (!value) return "Filename is required";
              if (!value.endsWith(".db")) return "Filename must end with .db";
              if (!/^[a-zA-Z0-9_.-]+$/.test(value))
                return "Filename contains invalid characters";
              return undefined;
            },
          }}
        >
          {(field) => (
            <div>
              <Label
                htmlFor="dataset-filename"
                className="mb-1 block font-medium"
              >
                Filename
              </Label>
              <TextInput
                id="dataset-filename"
                name={field.name}
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                placeholder="my_dataset.db"
                color={
                  field.state.meta.errors.length > 0 ? "failure" : undefined
                }
              />
              {field.state.meta.errors.length > 0 ? (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors.join(", ")}
                </div>
              ) : (
                <div className="mt-1 text-sm text-gray-500">
                  Must end with .db extension
                </div>
              )}
            </div>
          )}
        </form.Field>

        <div className="flex justify-end gap-2 pt-4">
          <Button
            type="submit"
            disabled={isSubmitting || !form.state.canSubmit}
          >
            {isSubmitting ? "Creating..." : "Create Dataset"}
          </Button>
        </div>
      </div>
    </form>
  );
};

export { DatasetForm };

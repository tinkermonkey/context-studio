import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Button, Alert, Label, Card } from "flowbite-react";
import { Info, FolderOpen } from "lucide-react";
import type { components } from "@/api/client/types";
import { useAddExistingDataset } from "@/api/hooks/datasets/useDatasetMutations";
import { useDatasetsDirectory } from "@/api/hooks/datasets";

type AddExistingDatasetRequest =
  components["schemas"]["AddExistingDatasetRequest"];

interface AddExistingDatasetFormProps {
  onSuccess?: (dataset: any) => void;
}

const AddExistingDatasetForm: React.FC<AddExistingDatasetFormProps> = ({
  onSuccess,
}) => {
  const addExistingDatasetMutation = useAddExistingDataset();
  const { data: directoryInfo, isLoading: directoryLoading } =
    useDatasetsDirectory();
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const form = useForm({
    defaultValues: {
      title: "",
      file_path: "",
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        // Construct the full path - if it doesn't start with /, assume it's relative to datasets directory
        let fullPath = value.file_path;
        if (
          directoryInfo?.datasets_directory &&
          !fullPath.startsWith("/") &&
          !fullPath.includes(":\\")
        ) {
          fullPath = `${directoryInfo.datasets_directory}/${fullPath}`;
        }

        const requestData = {
          ...value,
          file_path: fullPath,
        };

        const result = await addExistingDatasetMutation.mutateAsync(
          requestData as AddExistingDatasetRequest,
        );
        if (onSuccess) onSuccess(result);
        form.reset();
      } catch (error: any) {
        let message = "An error occurred";
        console.error("Full error object:", error);
        console.error("Error detail:", error?.detail);

        if (error?.response?.data?.detail) {
          if (Array.isArray(error.response.data.detail)) {
            // Validation errors from FastAPI
            const validationErrors = error.response.data.detail
              .map((err: any) => `${err.loc?.join(" > ")}: ${err.msg}`)
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

  const handleFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // For web file inputs, we'll use just the filename
      // The form will handle constructing the full path based on the datasets directory
      form.setFieldValue("file_path", file.name);
      // Auto-populate title with filename without extension if title is empty
      if (!form.getFieldValue("title")) {
        const nameWithoutExt = file.name.replace(/\.[^/.]+$/, "");
        form.setFieldValue("title", nameWithoutExt.replace(/[_-]/g, " "));
      }
    }
  };

  const isSubmitting = addExistingDatasetMutation.isPending;

  if (directoryLoading) {
    return <div>Loading datasets directory...</div>;
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      <div className="space-y-4">
        {directoryInfo?.datasets_directory && (
          <Card>
            <div className="text-sm">
              <p className="mb-1 font-medium text-gray-700">
                Datasets Directory:
              </p>
              <p className="font-mono text-xs break-all text-gray-600">
                {directoryInfo.datasets_directory}
              </p>
              <p className="mt-2 text-xs text-gray-500">
                Files will be looked for in this directory. You can enter just
                the filename if the file is in this directory, or provide a full
                path to a file elsewhere.
              </p>
            </div>
          </Card>
        )}

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
          name="file_path"
          validators={{
            onChange: ({ value }) => {
              if (!value) return "Please enter a file path or select a file";
              if (!value.endsWith(".db")) return "File must be a .db file";
              return undefined;
            },
          }}
        >
          {(field) => (
            <div>
              <Label
                htmlFor="dataset-file-path"
                className="mb-1 block font-medium"
              >
                Dataset File Path
              </Label>
              <div className="flex gap-2">
                <TextInput
                  id="dataset-file-path"
                  name={field.name}
                  value={field.state.value}
                  onBlur={field.handleBlur}
                  onChange={(e) => field.handleChange(e.target.value)}
                  placeholder="filename.db or /full/path/to/file.db"
                  color={
                    field.state.meta.errors.length > 0 ? "failure" : undefined
                  }
                  className="flex-1"
                />
                <Button
                  type="button"
                  color="light"
                  onClick={handleFileSelect}
                  className="whitespace-nowrap"
                >
                  <FolderOpen className="mr-2 h-4 w-4" />
                  Browse
                </Button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".db"
                onChange={handleFileChange}
                className="hidden"
              />
              {field.state.meta.errors.length > 0 ? (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors.join(", ")}
                </div>
              ) : (
                <div className="mt-1 text-sm text-gray-500">
                  Enter the filename if it's in the datasets directory, or
                  provide a full path
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
            {isSubmitting ? "Adding..." : "Add Dataset"}
          </Button>
        </div>
      </div>
    </form>
  );
};

export { AddExistingDatasetForm };

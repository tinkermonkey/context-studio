import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Alert, Label } from "flowbite-react";
import { X, GripVertical } from "lucide-react";
import type { components } from "@/api/client/types";
import {
  useCreateIndividual,
  useUpdateIndividual,
  useSetIndividualClasses,
} from "@/api/hooks/individuals";
import { useOntologyClasses } from "@/api/hooks/ontologyClasses";
import { renderShortUuid } from "@/utils/renderers";

type IndividualResponse = components["schemas"]["IndividualResponse"];
type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualUpdateRequest = components["schemas"]["IndividualUpdateRequest"];
type ClassResponse = components["schemas"]["ClassResponse"];

interface IndividualFormProps {
  onSuccess?: (individual: IndividualResponse) => void;
  individual?: IndividualResponse;
  onCancel?: () => void;
}

const IndividualForm: React.FC<IndividualFormProps> = ({
  onSuccess,
  individual,
  onCancel,
}) => {
  const createIndividualMutation = useCreateIndividual();
  const updateIndividualMutation = useUpdateIndividual();
  const setIndividualClassesMutation = useSetIndividualClasses();
  const { data: availableClasses = [] } = useOntologyClasses();
  const isEdit = !!individual;
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [selectedClassIds, setSelectedClassIds] = React.useState<string[]>(
    individual?.class_ids ?? [],
  );
  const [draggedIndex, setDraggedIndex] = React.useState<number | null>(null);

  const getDefaultValues = () => ({
    title: individual?.title ?? "",
    description: individual?.description ?? "",
  });

  const form = useForm({
    defaultValues: getDefaultValues(),
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      try {
        if (selectedClassIds.length === 0) {
          setSubmitError("At least one parent class is required");
          return;
        }

        if (isEdit && individual?.id) {
          // For edit: update the individual's title/description
          const updateData: IndividualUpdateRequest = {
            title: value.title,
            description: value.description || null,
          };

          await updateIndividualMutation.mutateAsync({
            id: individual.id,
            data: updateData,
          });

          // Then update class membership separately
          const result = await setIndividualClassesMutation.mutateAsync({
            id: individual.id,
            classIds: selectedClassIds,
          });

          if (onSuccess) onSuccess(result);
        } else {
          // For create: send class IDs in the create request
          const createData: IndividualCreateRequest = {
            title: value.title,
            description: value.description || null,
            class_ids: selectedClassIds,
          };

          const result = await createIndividualMutation.mutateAsync(createData);
          if (onSuccess) onSuccess(result);
        }

        form.reset();
      } catch (error: any) {
        console.error("Full error object:", error);
        console.error("Error detail:", error?.detail);

        // Try to extract the original API detail string from the error object
        const detail =
          error?.detail?.detail ||
          error?.response?.data?.detail ||
          error?.data?.detail ||
          error?.body?.detail ||
          error?.detail;

        let message: string;
        if (Array.isArray(detail)) {
          message = detail.map((d: any) => d.msg).join("; ");
        } else if (typeof detail === "string") {
          message = detail;
        } else if (error?.message) {
          message = error.message;
        } else if (typeof error === "string") {
          message = error;
        } else {
          message = JSON.stringify(error);
        }
        setSubmitError(message);
        console.error(
          isEdit ? "Failed to update individual:" : "Failed to create individual:",
          error,
        );
      }
    },
  });

  const handleAddClass = (classId: string) => {
    if (!selectedClassIds.includes(classId)) {
      setSelectedClassIds([...selectedClassIds, classId]);
    }
  };

  const handleRemoveClass = (classId: string) => {
    setSelectedClassIds(selectedClassIds.filter((id) => id !== classId));
  };

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = (dropIndex: number) => {
    if (draggedIndex === null || draggedIndex === dropIndex) {
      setDraggedIndex(null);
      return;
    }

    const newClassIds = [...selectedClassIds];
    const [movedClass] = newClassIds.splice(draggedIndex, 1);
    newClassIds.splice(dropIndex, 0, movedClass);
    setSelectedClassIds(newClassIds);
    setDraggedIndex(null);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  // Get the selected class objects
  const selectedClasses = selectedClassIds
    .map((id) => availableClasses.find((c) => c.id === id))
    .filter((c) => c !== undefined) as ClassResponse[];

  // Get available classes not yet selected
  const availableUnselectedClasses = availableClasses.filter(
    (c) => !selectedClassIds.includes(c.id),
  );

  return (
    <div
      className="flex flex-col gap-4"
      data-testid="individual-form"
    >
      {submitError && (
        <Alert color="failure">
          <span className="font-medium">Error:</span> {submitError}
        </Alert>
      )}

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
              <Label htmlFor="individual-title" className="mb-1 block font-medium">
                Title
              </Label>
              <TextInput
                id="individual-title"
                placeholder="Individual title"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                autoFocus
                data-testid="individual-title-input"
              />
            </div>
          )}
        </form.Field>

        <form.Field
          name="description"
        >
          {(field) => (
            <div>
              <Label
                htmlFor="individual-description"
                className="mb-1 block font-medium"
              >
                Description
              </Label>
              <Textarea
                id="individual-description"
                placeholder="Individual description (optional)"
                value={field.state.value}
                color={field.state.meta.errors.length ? "failure" : undefined}
                onChange={(e) => field.handleChange(e.target.value)}
                data-testid="individual-description-input"
              />
            </div>
          )}
        </form.Field>

        {/* Multi-Class Selector */}
        <div data-testid="individual-classes-selector">
          <Label className="mb-3 block font-medium">Parent Classes</Label>

          {/* Selected Classes List */}
          <div className="mb-4 space-y-2">
            {selectedClasses.length === 0 ? (
              <div className="rounded border border-dashed border-gray-300 p-4 text-center text-gray-500">
                No classes selected yet
              </div>
            ) : (
              selectedClasses.map((selectedClass, index) => (
                <div
                  key={selectedClass.id}
                  draggable
                  onDragStart={() => handleDragStart(index)}
                  onDragOver={handleDragOver}
                  onDrop={() => handleDrop(index)}
                  onDragEnd={handleDragEnd}
                  className={`flex items-center gap-2 rounded border p-3 transition-opacity ${
                    draggedIndex === index
                      ? "border-gray-300 bg-gray-100 opacity-50"
                      : "border-gray-200 bg-gray-50"
                  }`}
                >
                  <GripVertical
                    className="h-4 w-4 cursor-move text-gray-400"
                    data-testid={`individual-classes-reorder-handle-${selectedClass.id}`}
                  />
                  <div className="flex-1">
                    <div className="font-medium">{selectedClass.title}</div>
                    <div className="text-sm text-gray-500">
                      {renderShortUuid(selectedClass.id)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveClass(selectedClass.id)}
                    className="rounded p-1 text-red-600 hover:bg-red-50"
                    title="Remove class"
                    data-testid={`individual-classes-remove-button-${selectedClass.id}`}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Add Class Dropdown */}
          {availableUnselectedClasses.length > 0 && (
            <div className="flex gap-2">
              <select
                id="add-class-select"
                className="flex-1 rounded border border-gray-300 bg-white px-3 py-2 text-sm"
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) {
                    handleAddClass(e.target.value);
                    e.target.value = "";
                  }
                }}
              >
                <option value="">Select a class to add...</option>
                {availableUnselectedClasses.map((cls) => (
                  <option key={cls.id} value={cls.id}>
                    {cls.title} ({renderShortUuid(cls.id)})
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  const select = document.getElementById(
                    "add-class-select",
                  ) as HTMLSelectElement;
                  if (select.value) {
                    handleAddClass(select.value);
                    select.value = "";
                  }
                }}
                className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                data-testid="individual-classes-add-button"
              >
                Add
              </button>
            </div>
          )}
        </div>

        {/* Form Actions */}
        <div className="flex gap-2 pt-4">
          <button
            type="submit"
            className="flex-1 rounded bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
            data-testid="individual-form-submit"
          >
            {isEdit ? "Update Individual" : "Create Individual"}
          </button>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded border border-gray-300 px-4 py-2 font-medium text-gray-700 hover:bg-gray-50"
              data-testid="individual-form-cancel"
            >
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export { IndividualForm };

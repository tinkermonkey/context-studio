import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button } from "flowbite-react";
import type { LayerCreate } from "@/api/services/layers";
import { useCreateLayer } from "@/api/hooks/layers/useLayerMutations";

interface LayerFormProps {
  onSuccess?: (layer: any) => void;
}

const CreateLayerForm: React.FC<LayerFormProps> = ({ onSuccess }) => {
  const createLayerMutation = useCreateLayer();
  const form = useForm({
    defaultValues: {
      title: "",
      definition: "",
      primary_predicate: "",
    },
    onSubmit: async ({ value }) => {
      try {
        const newLayer = await createLayerMutation.mutateAsync(value as LayerCreate);
        if (onSuccess) onSuccess(newLayer);
        form.reset();
      } catch (error) {
        // TODO: Use useButterToast for error notification
        console.error("Failed to create layer:", error);
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
            <TextInput
              id="layer-title"
              placeholder="Title"
              value={field.state.value}
              color={field.state.meta.errors.length ? "failure" : undefined}
              onChange={(e) => field.handleChange(e.target.value)}
              required
              autoFocus
            />
          )}
        </form.Field>
        <form.Field name="definition">
          {(field) => (
            <Textarea
              id="layer-definition"
              placeholder="Definition (optional)"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
            />
          )}
        </form.Field>
        <form.Field name="primary_predicate">
          {(field) => (
            <TextInput
              id="layer-primary-predicate"
              placeholder="Primary Predicate (optional)"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
            />
          )}
        </form.Field>

        <div className="flex items-center gap-2">
          <Button type="submit" disabled={form.state.isSubmitting || createLayerMutation.isPending}>
            {form.state.isSubmitting || createLayerMutation.isPending ? "Creating..." : "Create Layer"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { CreateLayerForm };

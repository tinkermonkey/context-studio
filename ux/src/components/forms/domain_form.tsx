import React from "react";
import { useForm } from "@tanstack/react-form";
import { TextInput, Textarea, Button, Alert, Label } from "flowbite-react";
import { Info, Layers } from "lucide-react";
import type { DomainCreate, DomainOut } from "@/api/services/domains";
import type { LayerOut } from "@/api/services/layers";
import {
  useCreateDomain,
  useUpdateDomain,
} from "@/api/hooks/domains/useDomainMutations";
import { LayerSelector } from "@/components/node_selectors/layer_selector";
import { PredicateSelector } from "@/components/node_selectors/predicate_selector";
import { PredicateSetSelector } from "@/components/node_selectors/predicate_set_selector";

interface DomainFormProps {
  onSuccess?: (domain: DomainOut) => void;
  domain?: DomainOut; // For edit mode
  // Child form props
  parentLayerId?: string;
  parentLayer?: LayerOut; // Full object for better UX
  mode?: 'create' | 'edit' | 'child';
}

const DomainForm: React.FC<DomainFormProps> = ({ 
  onSuccess, 
  domain, 
  parentLayerId,
  parentLayer,
  mode = 'create'
}) => {
  const createDomainMutation = useCreateDomain();
  const updateDomainMutation = useUpdateDomain();
  const isEdit = !!domain;
  const isChildMode = mode === 'child' || !!parentLayerId;
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  
  const getDefaultValues = () => ({
    title: domain?.title ?? "",
    definition: domain?.definition ?? "",
    layer_id: domain?.layer_id ?? parentLayerId ?? "",
    primary_predicate_id: domain?.primary_predicate_id ?? "",
    predicate_set: domain?.predicate_set ?? [],
  });
  
  const form = useForm({
    defaultValues: getDefaultValues(),
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
        {/* Parent Context Display */}
        {isChildMode && parentLayer && (
          <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
              <Info className="h-4 w-4" />
              <span>Creating domain in layer:</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <Layers className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              <span className="font-semibold text-blue-900 dark:text-blue-100">
                {parentLayer.title}
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
        
        {/* Hide layer selector in child mode */}
        {!isChildMode && (
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
        )}

        {/* Predicate Fields */}
        <form.Field name="primary_predicate_id">
          {(field) => (
            <div>
              <Label htmlFor="domain-primary-predicate" className="mb-1 block font-medium">
                Structural Predicate (optional)
              </Label>
              <PredicateSelector
                value={field.state.value}
                onSelect={(predicate) => {
                  const predicateId = predicate?.id || "";
                  field.handleChange(predicateId);
                  
                  // Auto-add to predicate set if not already there
                  const currentSet = form.getFieldValue('predicate_set') || [];
                  if (predicateId && !currentSet.includes(predicateId)) {
                    form.setFieldValue('predicate_set', [...currentSet, predicateId]);
                  }
                }}
              />
              <p className="mt-1 text-sm text-gray-500">
                The predicate that defines this domain's core hierarchical relationships
              </p>
              {field.state.meta.errors.length > 0 && (
                <div className="mt-1 text-sm text-red-600">
                  {field.state.meta.errors[0]}
                </div>
              )}
            </div>
          )}
        </form.Field>

        <form.Field name="predicate_set">
          {(field) => (
            <div>
              <Label htmlFor="domain-predicate-set" className="mb-1 block font-medium">
                Additional Predicates (optional)
              </Label>
              <PredicateSetSelector
                value={field.state.value || []}
                onSelectionChange={(predicateIds) => {
                  field.handleChange(predicateIds);
                }}
              />
                            
              <p className="mt-1 text-sm text-gray-500">
                Predicates that can be used with this domain
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
                : isChildMode
                  ? "Create Domain"
                  : "Create Domain"}
          </Button>
        </div>
      </form>
    </>
  );
};

export { DomainForm };

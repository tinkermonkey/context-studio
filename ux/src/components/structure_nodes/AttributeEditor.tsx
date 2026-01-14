/**
 * Attribute Editor Component
 *
 * Form for adding/editing structure node attributes
 */

import React, { useState } from "react";
import { useForm } from "@tanstack/react-form";
import {
  TextInput,
  Button,
  Label,
  Select,
  Card,
  Alert,
} from "flowbite-react";
import { AlertCircle, Plus, X } from "lucide-react";
import type {
  StructureNodeAttribute,
  AttributeValueType,
} from "@/api/types/structureNodes";
import { AttributeValueInput } from "./AttributeValueInput";

interface AttributeEditorProps {
  onSave: (attribute: StructureNodeAttribute) => Promise<void>;
  isLoading?: boolean;
  initialAttribute?: StructureNodeAttribute;
  onCancel?: () => void;
  existingKeys?: string[];
}

const ATTRIBUTE_TYPES: AttributeValueType[] = [
  "string",
  "number",
  "boolean",
  "date",
  "url",
];

const validateKey = (key: string, existingKeys?: string[]): string | null => {
  if (!key.trim()) {
    return "Key is required";
  }

  if (!/^[a-z][a-z0-9_]*$/.test(key)) {
    return "Key must start with a letter and contain only lowercase alphanumeric characters and underscores";
  }

  if (existingKeys?.includes(key)) {
    return "This key already exists";
  }

  return null;
};

const validateUrl = (url: string): string | null => {
  if (!url) return null;

  try {
    new URL(url);
    return null;
  } catch {
    return "Invalid URL format";
  }
};

const validateValue = (
  value: unknown,
  valueType: AttributeValueType,
): string | null => {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  switch (valueType) {
    case "number":
      if (typeof value !== "number" && isNaN(Number(value))) {
        return "Invalid number";
      }
      return null;

    case "date": {
      const strValue = String(value);
      if (!strValue) return null;
      const date = new Date(strValue);
      if (isNaN(date.getTime())) {
        return "Invalid date format";
      }
      return null;
    }

    case "url":
      return validateUrl(String(value));

    default:
      return null;
  }
};

export const AttributeEditor: React.FC<AttributeEditorProps> = ({
  onSave,
  isLoading = false,
  initialAttribute,
  onCancel,
  existingKeys = [],
}) => {
  const isEdit = !!initialAttribute;
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string>
  >({});

  const form = useForm({
    defaultValues: {
      key: initialAttribute?.key ?? "",
      title: initialAttribute?.title ?? "",
      value_type: (initialAttribute?.value_type ?? "string") as AttributeValueType,
      value: initialAttribute?.value ?? null,
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      const errors: Record<string, string> = {};

      const keyError = validateKey(
        value.key,
        isEdit ? undefined : existingKeys,
      );
      if (keyError) errors.key = keyError;

      const valueError = validateValue(value.value, value.value_type);
      if (valueError) errors.value = valueError;

      if (Object.keys(errors).length > 0) {
        setValidationErrors(errors);
        return;
      }

      setValidationErrors({});

      try {
        await onSave({
          key: value.key,
          title: value.title,
          value_type: value.value_type,
          value: value.value,
        });
        form.reset();
      } catch (error: any) {
        const message =
          error?.message ||
          error?.detail ||
          "Failed to save attribute";
        setSubmitError(message);
        console.error("Failed to save attribute:", error);
      }
    },
  });

  return (
    <Card className="bg-gray-50 border border-gray-200">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          form.handleSubmit();
        }}
        className="space-y-4"
      >
        {submitError && (
          <Alert color="failure" icon={AlertCircle}>
            <div>
              <span className="font-medium">Error</span>
              <div className="text-sm">{submitError}</div>
            </div>
          </Alert>
        )}

        <div>
          <Label htmlFor="key" className="mb-2 block">
            Key
          </Label>
          <form.Field
            name="key"
            children={(field) => (
              <>
                <TextInput
                  id="key"
                  type="text"
                  placeholder="attribute_key"
                  disabled={isEdit || isLoading}
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  color={validationErrors.key ? "failure" : undefined}
                  sizing="sm"
                />
                {validationErrors.key && (
                  <div className="mt-1 text-sm text-red-600 flex items-center gap-1">
                    <AlertCircle className="h-4 w-4" />
                    {validationErrors.key}
                  </div>
                )}
              </>
            )}
          />
        </div>

        <div>
          <Label htmlFor="title" className="mb-2 block">
            Title
          </Label>
          <form.Field
            name="title"
            children={(field) => (
              <TextInput
                id="title"
                type="text"
                placeholder="Display name"
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                disabled={isLoading}
                sizing="sm"
              />
            )}
          />
        </div>

        <div>
          <Label htmlFor="value_type" className="mb-2 block">
            Type
          </Label>
          <form.Field
            name="value_type"
            children={(field) => (
              <Select
                id="value_type"
                value={field.state.value}
                onChange={(e) =>
                  field.handleChange(e.target.value as AttributeValueType)
                }
                disabled={isEdit || isLoading}
                sizing="sm"
              >
                {ATTRIBUTE_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </Select>
            )}
          />
        </div>

        <form.Field
          name="value_type"
          children={(typeField) => (
            <form.Field
              name="value"
              children={(field) => (
                <div>
                  <Label htmlFor="value" className="mb-2 block">
                    Value
                  </Label>
                  <AttributeValueInput
                    value={field.state.value}
                    valueType={typeField.state.value}
                    onChange={(newValue) => field.handleChange(newValue as any)}
                    error={validationErrors.value}
                    disabled={isLoading}
                  />
                </div>
              )}
            />
          )}
        />

        <div className="flex gap-2 justify-end">
          {onCancel && (
            <Button
              type="button"
              color="light"
              onClick={onCancel}
              disabled={isLoading}
            >
              <X className="h-4 w-4 mr-1" />
              Cancel
            </Button>
          )}
          <Button type="submit" color="blue" disabled={isLoading}>
            <Plus className="h-4 w-4 mr-1" />
            {isEdit ? "Update" : "Add"} Attribute
          </Button>
        </div>
      </form>
    </Card>
  );
};

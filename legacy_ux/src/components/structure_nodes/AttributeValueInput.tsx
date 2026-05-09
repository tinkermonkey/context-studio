/**
 * Attribute Value Input Component
 *
 * Type-specific input component for attribute values
 */

import React from "react";
import { TextInput, Checkbox, HelperText, Label } from "flowbite-react";
import { AlertCircle } from "lucide-react";
import type { AttributeValueType } from "@/api/types/ontology";

interface AttributeValueInputProps {
  value: unknown;
  valueType: AttributeValueType;
  onChange: (value: unknown) => void;
  error?: string;
  disabled?: boolean;
  placeholder?: string;
}

export const AttributeValueInput: React.FC<AttributeValueInputProps> = ({
  value,
  valueType,
  onChange,
  error,
  disabled = false,
  placeholder,
}) => {
  const stringValue = String(value ?? "");

  const renderInput = () => {
    switch (valueType) {
      case "string":
        return (
          <TextInput
            type="text"
            value={stringValue}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder || "Enter text value"}
            disabled={disabled}
            color={error ? "failure" : undefined}
            sizing="sm"
          />
        );

      case "number":
        return (
          <TextInput
            type="number"
            value={stringValue}
            onChange={(e) => {
              const numValue =
                e.target.value === "" ? null : Number(e.target.value);
              onChange(numValue);
            }}
            placeholder={placeholder || "Enter numeric value"}
            disabled={disabled}
            color={error ? "failure" : undefined}
            sizing="sm"
          />
        );

      case "boolean":
        return (
          <div className="flex items-center gap-2">
            <Checkbox
              checked={value === true || value === "true"}
              onChange={(e) => onChange(e.target.checked)}
              disabled={disabled}
            />
            <Label className="text-sm">
              {value === true || value === "true" ? "True" : "False"}
            </Label>
          </div>
        );

      case "date":
        return (
          <TextInput
            type="date"
            value={stringValue}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder || "Select date"}
            disabled={disabled}
            color={error ? "failure" : undefined}
            sizing="sm"
          />
        );

      case "url":
        return (
          <TextInput
            type="url"
            value={stringValue}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder || "https://example.com"}
            disabled={disabled}
            color={error ? "failure" : undefined}
            sizing="sm"
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-1">
      {renderInput()}
      {error && (
        <HelperText color="failure">
          <div className="flex items-center gap-1">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        </HelperText>
      )}
    </div>
  );
};

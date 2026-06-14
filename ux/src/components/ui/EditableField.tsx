import { useState, useRef } from "react";
import { TextInput, TextArea, NumberInput, Select } from "@tinkermonkey/heimdall-ui";

type SaveStatus = "idle" | "saving" | "saved" | "error";
type FieldKind = "TextInput" | "TextArea" | "NumberInput" | "Select";

export interface SelectOption {
  value: string;
  label: string;
}

interface EditableFieldProps {
  label: string;
  value: string;
  onSave: (value: string) => void | Promise<void>;
  kind?: FieldKind;
  options?: SelectOption[];
  disabled?: boolean;
  validate?: (value: string) => string | undefined;
  mono?: boolean;
  rows?: number;
  placeholder?: string;
  "data-testid"?: string;
}

export function EditableField({
  label,
  value,
  onSave,
  kind = "TextInput",
  options,
  disabled,
  validate,
  mono,
  rows = 3,
  placeholder,
  "data-testid": testId,
}: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [saveError, setSaveError] = useState<string | undefined>();
  const [validationError, setValidationError] = useState<string | undefined>();
  const savedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  const startEditing = () => {
    if (disabled) return;
    setEditValue(value);
    setValidationError(undefined);
    setIsEditing(true);
  };

  const handleChange = (newValue: string) => {
    setEditValue(newValue);
    if (validationError) {
      setValidationError(validate?.(newValue));
    }
  };

  const performSave = async (val: string) => {
    setSaveError(undefined);
    setSaveStatus("saving");
    try {
      await onSave(val);
      setSaveStatus("saved");
      setIsEditing(false);
      if (savedTimeoutRef.current) clearTimeout(savedTimeoutRef.current);
      savedTimeoutRef.current = setTimeout(() => setSaveStatus("idle"), 1600);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Save failed";
      setSaveError(message);
      setSaveStatus("error");
      // Stay in edit mode and return focus so the user can correct and retry.
      setIsEditing(true);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  };

  const handleBlur = async () => {
    const trimmed = kind === "NumberInput" ? editValue : editValue.trim();
    const err = validate?.(trimmed);
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError(undefined);

    if (trimmed === value) {
      setIsEditing(false);
      return;
    }

    // Keep edit mode active during the save; performSave exits on success or
    // restores focus on failure.
    await performSave(trimmed);
  };

  const handleSelectChange = async (newValue: string) => {
    setEditValue(newValue);
    setIsEditing(false);
    if (newValue === value) return;
    await performSave(newValue);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setEditValue(value);
      setIsEditing(false);
      setValidationError(undefined);
    } else if (e.key === "Enter" && kind !== "TextArea") {
      (e.target as HTMLElement).blur();
    }
  };

  const renderInput = () => {
    const inputTestId = testId ? `${testId}-input` : undefined;

    switch (kind) {
      case "TextArea":
        return (
          <TextArea
            ref={inputRef as any}
            value={editValue}
            onChange={(e) => handleChange(e.target.value)}
            onBlur={() => void handleBlur()}
            onKeyDown={handleKeyDown}
            rows={rows}
            placeholder={placeholder}
            autoFocus
            data-testid={inputTestId}
          />
        );
      case "NumberInput":
        return (
          <NumberInput
            ref={inputRef as any}
            value={editValue}
            onChange={(e) => handleChange(e.target.value)}
            onBlur={() => void handleBlur()}
            onKeyDown={handleKeyDown}
            mono={mono}
            placeholder={placeholder}
            autoFocus
            data-testid={inputTestId}
          />
        );
      case "Select":
        return (
          <Select
            value={editValue}
            onChange={(v) => void handleSelectChange(v)}
            data-testid={inputTestId}
          >
            {options?.map((opt) => (
              <Select.Item key={opt.value} value={opt.value}>
                {opt.label}
              </Select.Item>
            ))}
          </Select>
        );
      default:
        return (
          <TextInput
            ref={inputRef as any}
            type="text"
            value={editValue}
            onChange={(e) => handleChange(e.target.value)}
            onBlur={() => void handleBlur()}
            onKeyDown={handleKeyDown}
            mono={mono}
            placeholder={placeholder}
            autoFocus
            data-testid={inputTestId}
          />
        );
    }
  };

  const displayValue =
    kind === "Select" && options
      ? (options.find((opt) => opt.value === value)?.label ?? value)
      : value;

  return (
    <div className="editable-field" data-testid={testId}>
      <div className="editable-field__header">
        <label className="form-group-label">{label}</label>
        {saveStatus === "saved" && (
          <span
            className="editable-field__saved-indicator"
            data-testid={testId ? `${testId}-saved` : undefined}
          >
            Saved
          </span>
        )}
        {saveStatus === "error" && (
          <span
            className="editable-field__error-indicator"
            role="alert"
            data-testid={testId ? `${testId}-error` : undefined}
          >
            {saveError ?? "Save failed"}
          </span>
        )}
      </div>

      {isEditing ? (
        <>
          {renderInput()}
          {validationError && (
            <div className="editable-field__validation-error" role="alert">
              {validationError}
            </div>
          )}
        </>
      ) : (
        <div
          className={`editable-field__view${disabled ? " editable-field__view--disabled" : ""}`}
          onClick={startEditing}
          onKeyDown={(e) => e.key === "Enter" && startEditing()}
          role={disabled ? undefined : "button"}
          tabIndex={disabled ? undefined : 0}
          aria-label={disabled ? undefined : `Edit ${label}`}
          data-testid={testId ? `${testId}-view` : undefined}
        >
          {displayValue || (
            <span className="editable-field__placeholder">{placeholder ?? "—"}</span>
          )}
        </div>
      )}
    </div>
  );
}

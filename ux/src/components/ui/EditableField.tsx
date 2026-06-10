import { useState, useRef } from "react";
import { TextInput, TextArea } from "@tinkermonkey/heimdall-ui";

type SaveStatus = "idle" | "saving" | "saved" | "error";

interface EditableFieldProps {
  label: string;
  value: string;
  onSave: (value: string) => void | Promise<void>;
  type?: "text" | "textarea";
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
  type = "text",
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
  const [validationError, setValidationError] = useState<string | undefined>();
  const savedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  const handleBlur = async () => {
    const trimmed = editValue.trim();
    const err = validate?.(trimmed);
    if (err) {
      setValidationError(err);
      return;
    }

    setIsEditing(false);
    setValidationError(undefined);

    if (trimmed === value) return;

    setSaveStatus("saving");
    try {
      await onSave(trimmed);
      setSaveStatus("saved");
      if (savedTimeoutRef.current) clearTimeout(savedTimeoutRef.current);
      savedTimeoutRef.current = setTimeout(() => setSaveStatus("idle"), 1600);
    } catch {
      setSaveStatus("error");
      setIsEditing(true);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setEditValue(value);
      setIsEditing(false);
      setValidationError(undefined);
    } else if (e.key === "Enter" && type !== "textarea") {
      (e.target as HTMLElement).blur();
    }
  };

  return (
    <div className="editable-field" data-testid={testId}>
      <div className="editable-field__header">
        <label className="form-group-label">{label}</label>
        {saveStatus === "saved" && (
          <span className="editable-field__saved-indicator" data-testid={testId ? `${testId}-saved` : undefined}>
            Saved
          </span>
        )}
        {saveStatus === "error" && (
          <span className="editable-field__error-indicator">Save failed</span>
        )}
      </div>

      {isEditing ? (
        <>
          {type === "textarea" ? (
            <TextArea
              value={editValue}
              onChange={(e) => handleChange(e.target.value)}
              onBlur={() => void handleBlur()}
              onKeyDown={handleKeyDown}
              rows={rows}
              placeholder={placeholder}
              autoFocus
              data-testid={testId ? `${testId}-input` : undefined}
            />
          ) : (
            <TextInput
              type="text"
              value={editValue}
              onChange={(e) => handleChange(e.target.value)}
              onBlur={() => void handleBlur()}
              onKeyDown={handleKeyDown}
              mono={mono}
              placeholder={placeholder}
              autoFocus
              data-testid={testId ? `${testId}-input` : undefined}
            />
          )}
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
          {value || (
            <span className="editable-field__placeholder">{placeholder ?? "—"}</span>
          )}
        </div>
      )}
    </div>
  );
}

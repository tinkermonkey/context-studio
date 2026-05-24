import { TextInput as Input, Select, Button, Modal } from "@tinkermonkey/heimdall-ui";
import { useState, useEffect, useRef } from "react";


import { COPY } from "@/routes/app/settings/copy";

export interface ConfigField {
  key: string;
  label: string;
  placeholder?: string;
  type?: "text" | "email" | "password" | "url" | "number";
  required?: boolean;
  sensitive?: boolean;
  readOnly?: boolean;
  options?: { label: string; value: string }[];
}

interface EditConfigModalProps {
  open: boolean;
  onClose: () => void;
  section: string;
  title: string;
  fields: ConfigField[];
  values: { [key: string]: unknown };
  onSave: (updates: { [key: string]: unknown }) => Promise<void>;
  isLoading?: boolean;
}

export function EditConfigModal({
  open,
  onClose,
  section,
  title,
  fields,
  values,
  onSave,
  isLoading,
}: EditConfigModalProps) {
  const [formState, setFormState] = useState<{ [key: string]: unknown }>(values);
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [isSaving, setIsSaving] = useState(false);
  const clearedSensitiveFields = useRef<Set<string>>(new Set());

  useEffect(() => {
    setFormState(values);
    setErrors({});
    clearedSensitiveFields.current = new Set();
  }, [values, open]);

  const handleChange = (key: string, value: unknown) => {
    setFormState((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) {
      setErrors((prev) => ({ ...prev, [key]: "" }));
    }
  };

  const handleSensitiveFieldFocus = (key: string) => {
    if (!clearedSensitiveFields.current.has(key) && formState[key]) {
      clearedSensitiveFields.current.add(key);
      setFormState((prev) => ({ ...prev, [key]: "" }));
    }
  };

  const calculateDiff = () => {
    const diff: { [key: string]: unknown } = {};
    Object.keys(formState).forEach((key) => {
      if (JSON.stringify(formState[key]) !== JSON.stringify(values[key])) {
        diff[key] = formState[key];
      }
    });
    return diff;
  };

  const handleSave = async () => {
    const newErrors: { [key: string]: string } = {};

    fields.forEach((field) => {
      if (field.required && !formState[field.key]) {
        newErrors[field.key] = `${field.label} is required`;
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const diff = calculateDiff();

    if (Object.keys(diff).length === 0) {
      onClose();
      return;
    }

    setIsSaving(true);
    try {
      await onSave(diff);
      onClose();
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : COPY.failedToSaveSettings;
      setErrors({ _form: errorMsg });
    } finally {
      setIsSaving(false);
    }
  };

  const footer = (
    <div className="form-actions">
      <Button variant="ghost" onClick={onClose} disabled={isSaving}>
        {COPY.cancelButton}
      </Button>
      <Button
        variant="primary"
        onClick={handleSave}
        disabled={isSaving || isLoading}
        data-testid={`${section.toLowerCase()}-edit-modal-save`}
      >
        {isSaving ? COPY.savingButton : COPY.saveButton}
      </Button>
    </div>
  );

  return (
    <Modal isOpen={open}
      onClose={onClose}
      title={title}
      footer={footer} data-testid="edit-config-modal"
    >
      <div className="stack-lg">
        {errors._form && <div className="form-error">{errors._form}</div>}

        {fields.map((field) => (
          <div key={field.key}>
            <label className="form-group-label">
              {field.label}
              {field.required && <span style={{ color: "var(--error-fg)" }}>*</span>}
            </label>

            {field.options ? (
              <Select
                value={String(formState[field.key] || "")}
                onChange={(e) => handleChange(field.key, e.target.value)}
                disabled={field.readOnly || isSaving}
                data-testid={`${section.toLowerCase()}-${field.key}-select`}
                aria-label={field.label}
                aria-required={field.required}
              >
                <option value="">{COPY.selectOptionPlaceholder}</option>
                {field.options.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                type={field.sensitive ? "password" : field.type || "text"}
                placeholder={
                  field.sensitive && formState[field.key]
                    ? COPY.sensitiveFieldPlaceholder
                    : field.placeholder
                }
                value={String(formState[field.key] || "")}
                onChange={(e) => handleChange(field.key, e.target.value)}
                onFocus={() => field.sensitive && handleSensitiveFieldFocus(field.key)}
                readOnly={field.readOnly}
                disabled={isSaving}
                mono={field.type === "password" || field.type === "email"}
                data-testid={`${section.toLowerCase()}-${field.key}-input`}
                aria-label={field.label}
                aria-required={field.required}
                aria-invalid={!!errors[field.key]}
                aria-describedby={errors[field.key] ? `${field.key}-error` : undefined}
              />
            )}

            {errors[field.key] && (
              <div className="field-error" id={`${field.key}-error`}>
                {errors[field.key]}
              </div>
            )}
          </div>
        ))}
      </div>
    </Modal>
  );
}

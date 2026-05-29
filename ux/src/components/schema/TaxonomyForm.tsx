import { TextInput as Input, TextArea as Textarea, Field, Button } from "@tinkermonkey/heimdall-ui";
import { useState } from "react";

import type { components } from "@/api/types";

type TaxonomyCreateRequest = components["schemas"]["TaxonomyCreateRequest"];

interface TaxonomyFormProps {
  onSubmit: (data: TaxonomyCreateRequest) => Promise<void>;
  isLoading?: boolean;
}

const IDENTIFIER_PATTERN = /^[a-z][a-z0-9_]{1,63}$/;
const HEX_COLOR_PATTERN = /^#[0-9a-f]{6}$/i;

function slugifyTitle(title: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
  if (!slug) return "";
  return slug[0] >= "a" && slug[0] <= "z" ? `tax_${slug}` : `tax_${slug}`;
}

export function TaxonomyForm({ onSubmit, isLoading }: TaxonomyFormProps) {
  const [identifier, setIdentifier] = useState("");
  const [identifierTouched, setIdentifierTouched] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState("");
  const [identifierError, setIdentifierError] = useState<string>();
  const [titleError, setTitleError] = useState<string>();
  const [colorError, setColorError] = useState<string>();
  const [formError, setFormError] = useState<string>();

  const validateIdentifier = (value: string): boolean => {
    if (!value.trim()) {
      setIdentifierError("Identifier is required");
      return false;
    }
    if (!IDENTIFIER_PATTERN.test(value.trim())) {
      setIdentifierError(
        "2–64 chars; lowercase letters, digits, underscores; must start with a letter",
      );
      return false;
    }
    setIdentifierError(undefined);
    return true;
  };

  const validateTitle = (value: string): boolean => {
    if (!value.trim()) {
      setTitleError("Title is required");
      return false;
    }
    setTitleError(undefined);
    return true;
  };

  const validateColor = (value: string): boolean => {
    if (!value) {
      setColorError(undefined);
      return true;
    }
    if (!HEX_COLOR_PATTERN.test(value)) {
      setColorError("Color must be a hex string like '#a3f2e4'");
      return false;
    }
    setColorError(undefined);
    return true;
  };

  const handleTitleChange = (value: string) => {
    setTitle(value);
    setTitleError(undefined);
    if (!identifierTouched) {
      const auto = slugifyTitle(value);
      setIdentifier(auto);
      setIdentifierError(undefined);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(undefined);

    const okTitle = validateTitle(title);
    const okIdentifier = validateIdentifier(identifier);
    const okColor = validateColor(color);
    if (!okTitle || !okIdentifier || !okColor) {
      return;
    }

    try {
      await onSubmit({
        identifier: identifier.trim().toLowerCase(),
        title,
        description: description || null,
        color: color ? color.toLowerCase() : null,
      });
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Failed to create taxonomy");
    }
  };

  return (
    <form onSubmit={handleSubmit} data-testid="taxonomy-form">
      <div className="stack-lg">
        {formError && (
          <div className="error-banner" role="alert" data-testid="taxonomy-form-error">
            {formError}
          </div>
        )}
        <Field label="Title" required error={titleError}>
          <Input
            type="text"
            placeholder="Taxonomy name"
            value={title}
            onChange={(e) => handleTitleChange(e.target.value)}
            onBlur={() => validateTitle(title)}
            data-testid="taxonomy-title-input"
          />
        </Field>

        <Field
          label="Identifier"
          required
          error={identifierError}
          hint="Lowercase slug, e.g. tax_life. Auto-filled from the title; edit to override."
        >
          <Input
            type="text"
            placeholder="tax_life"
            value={identifier}
            onChange={(e) => {
              setIdentifier(e.target.value);
              setIdentifierTouched(true);
              setIdentifierError(undefined);
            }}
            onBlur={() => validateIdentifier(identifier)}
            data-testid="taxonomy-identifier-input"
          />
        </Field>

        <Field label="Description (optional)">
          <Textarea
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="taxonomy-description-input"
            rows={4}
          />
        </Field>

        <Field label="Color (optional)" error={colorError} hint="Hex like #a3f2e4">
          <div className="taxonomy-form-color-row">
            <input
              type="color"
              className="taxonomy-form-color-swatch"
              value={color || "#888888"}
              onChange={(e) => {
                setColor(e.target.value);
                setColorError(undefined);
              }}
              aria-label="Pick a color"
              data-testid="taxonomy-color-picker"
            />
            <Input
              type="text"
              placeholder="#a3f2e4"
              value={color}
              onChange={(e) => {
                setColor(e.target.value);
                setColorError(undefined);
              }}
              onBlur={() => validateColor(color)}
              data-testid="taxonomy-color-input"
            />
          </div>
        </Field>

        <Button
          type="submit"
          variant="primary"
          disabled={isLoading}
          data-testid="taxonomy-submit-button"
        >
          Create Taxonomy
        </Button>
      </div>
    </form>
  );
}

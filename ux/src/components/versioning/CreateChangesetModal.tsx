import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { TextareaHTMLAttributes, InputHTMLAttributes } from "react";

interface CreateChangesetModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string, description?: string) => void;
  isLoading: boolean;
  selectedCount: number;
}

function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className="input" style={{ resize: "vertical", ...props.style }} />;
}

export function CreateChangesetModal({
  open,
  onClose,
  onSubmit,
  isLoading,
  selectedCount,
}: CreateChangesetModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState<string | undefined>();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validate
    if (!name.trim()) {
      setNameError("Changeset name is required");
      return;
    }

    onSubmit(name.trim(), description.trim() || undefined);

    // Reset form
    setName("");
    setDescription("");
    setNameError(undefined);
  };

  const handleNameChange = (value: string) => {
    setName(value);
    if (nameError) {
      setNameError(undefined);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create Changeset"
      size="md"
    >
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {/* Info */}
        <p style={{ fontSize: "13px", color: "var(--canvas-fg-2)", margin: 0 }}>
          Creating changeset with <strong>{selectedCount}</strong> change{selectedCount !== 1 ? "s" : ""}
        </p>

        {/* Name field */}
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <label
            style={{
              fontSize: "12px",
              fontWeight: 500,
              color: "var(--canvas-fg)",
              margin: 0,
            }}
            htmlFor="changeset-name"
          >
            Changeset Name
          </label>
          <Input
            id="changeset-name"
            data-testid="changeset-name-input"
            type="text"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="e.g., Add new properties to Person class"
            autoFocus
            disabled={isLoading}
          />
          {nameError && (
            <span style={{ fontSize: "12px", color: "#ef4444", margin: 0 }}>
              {nameError}
            </span>
          )}
        </div>

        {/* Description field */}
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <label
            style={{
              fontSize: "12px",
              fontWeight: 500,
              color: "var(--canvas-fg)",
              margin: 0,
            }}
            htmlFor="changeset-description"
          >
            Description (optional)
          </label>
          <Textarea
            id="changeset-description"
            data-testid="changeset-description-input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the changes in this changeset..."
            rows={3}
            disabled={isLoading}
          />
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: "8px" }}>
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isLoading}
            data-testid="changeset-cancel-button"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={isLoading || !name.trim()}
            data-testid="changeset-submit-button"
          >
            {isLoading ? "Creating..." : "Create Changeset"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

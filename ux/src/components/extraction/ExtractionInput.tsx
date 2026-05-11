import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useToasts } from "@/components/ui/Toast";

interface ExtractionInputProps {
  onExtract: (text: string) => void;
  isLoading?: boolean;
}

export function ExtractionInput({ onExtract, isLoading = false }: ExtractionInputProps) {
  const [text, setText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToasts();

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      let content = "";
      if (file.type === "application/pdf") {
        toast("warning", "PDF support coming soon", "Please paste text or upload .txt/.md files.");
        return;
      } else {
        // Read text and markdown files
        content = await file.text();
      }
      setText(content);
    } catch (error) {
      console.error("Failed to read file:", error);
      toast("error", "Failed to read file", "Please try again.");
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleExtract = () => {
    if (text.trim()) {
      onExtract(text);
    }
  };

  const characterCount = text.length;
  const isDisabled = !text.trim() || isLoading;

  return (
    <div className="panel" data-testid="extraction-input">
      <div className="panel-head">
        <span className="panel-title">Input</span>
      </div>
      <div className="panel-body">
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste text here to extract entities, relationships, and embeddings..."
            rows={8}
            style={{ resize: "vertical" }}
          />

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: "var(--text-sm)",
              color: "var(--canvas-fg-2)",
            }}
          >
            <span>{characterCount} characters</span>
          </div>

          <div style={{ display: "flex", gap: "8px", flexDirection: "column" }}>
            <Button
              variant="primary"
              onClick={handleExtract}
              disabled={isDisabled}
              style={{ width: "100%" }}
              aria-busy={isLoading}
            >
              {isLoading ? "Extracting..." : "Extract"}
            </Button>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              className="btn btn-ghost"
              style={{ width: "100%", cursor: "pointer" }}
              aria-label="Upload a file (.txt, .md, .pdf) to extract entities"
            >
              <Upload size={16} style={{ marginRight: "8px" }} />
              Or upload a file (.txt, .md, .pdf)
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.pdf"
              onChange={handleFileUpload}
              style={{ display: "none" }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { TextArea as Textarea } from "@tinkermonkey/heimdall-ui";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { COPY } from "@/routes/app/extraction/-copy";

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
        toast("warning", COPY.PDF_SUPPORT_WARNING, COPY.PDF_SUPPORT_HINT);
        return;
      } else {
        // Read text and markdown files
        content = await file.text();
      }
      setText(content);
    } catch (error) {
      console.error("Failed to read file:", error);
      toast("error", COPY.FILE_READ_ERROR, COPY.FILE_READ_RETRY);
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
        <span className="panel-title">{COPY.INPUT_PANEL_TITLE}</span>
      </div>
      <div className="panel-body">
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={COPY.INPUT_PLACEHOLDER}
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
            <span>
              {characterCount} {COPY.CHARACTERS_LABEL}
            </span>
          </div>

          <div style={{ display: "flex", gap: "8px", flexDirection: "column" }}>
            <Button
              variant="primary"
              onClick={handleExtract}
              disabled={isDisabled}
              style={{ width: "100%" }}
              aria-busy={isLoading}
            >
              {isLoading ? COPY.EXTRACTING_BUTTON : COPY.EXTRACT_BUTTON}
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
              {COPY.UPLOAD_FILE_BUTTON}
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

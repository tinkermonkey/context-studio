/**
 * Import Panel
 *
 * Form for importing ontology data from a file
 */

import React from "react";
import { Button, Card, Label, Select } from "flowbite-react";
import { Upload } from "lucide-react";
import { useButterToast } from "@/hooks/useButterToast";

type ImportFormat = "skos" | "owl" | "graphml" | "auto";

interface ImportPanelProps {
  onPreviewRequested?: (file: File, format: ImportFormat) => void;
}

export function ImportPanel({ onPreviewRequested }: ImportPanelProps) {
  const { info, error } = useButterToast();
  const [dragActive, setDragActive] = React.useState(false);
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [format, setFormat] = React.useState<ImportFormat>("auto");
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const detectFormatFromFile = (file: File): ImportFormat => {
    const ext = file.name.split(".").pop()?.toLowerCase();
    switch (ext) {
      case "rdf":
      case "xml":
        return "owl";
      case "graphml":
        return "graphml";
      case "ttl":
      case "n3":
        return "skos";
      default:
        return "auto";
    }
  };

  const handleDrag = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      const file = files[0];
      setSelectedFile(file);
      const detectedFormat = detectFormatFromFile(file);
      setFormat(detectedFormat);
      info(`File selected: ${file.name} (detected as ${detectedFormat})`);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files[0]) {
      const file = files[0];
      setSelectedFile(file);
      const detectedFormat = detectFormatFromFile(file);
      setFormat(detectedFormat);
      info(`File selected: ${file.name}`);
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handlePreview = () => {
    if (!selectedFile) {
      error("Please select a file first");
      return;
    }
    onPreviewRequested?.(selectedFile, format);
  };

  return (
    <div data-testid="interchange-import-panel" className="space-y-6">
      <Card>
        <h3 className="mb-4 text-lg font-semibold">Import File</h3>

        {/* Drag-drop area */}
        <div
          data-testid="interchange-import-file-input"
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition ${
            dragActive
              ? "border-blue-400 bg-blue-50 dark:bg-blue-950"
              : "border-gray-300 hover:border-gray-400 dark:border-gray-600"
          }`}
          onClick={handleClick}
        >
          <Upload className="mx-auto mb-2 h-8 w-8 text-gray-400" />
          <p className="text-gray-700 dark:text-gray-300">
            Drag and drop your file here, or{" "}
            <button className="text-blue-500 underline hover:text-blue-700">
              click to browse
            </button>
          </p>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Supported formats: SKOS (TTL, N3), OWL (RDF, XML), GraphML
          </p>
          <input
            ref={fileInputRef}
            type="file"
            hidden
            onChange={handleFileChange}
            accept=".rdf,.xml,.ttl,.n3,.graphml"
          />
        </div>

        {selectedFile && (
          <div className="mt-4 rounded border border-blue-200 bg-blue-50 p-3 dark:border-blue-800 dark:bg-blue-950">
            <p className="text-sm font-semibold text-blue-900 dark:text-blue-100">
              Selected: {selectedFile.name}
            </p>
            <p className="mt-1 text-xs text-blue-700 dark:text-blue-300">
              Size: {(selectedFile.size / 1024).toFixed(2)} KB
            </p>
          </div>
        )}
      </Card>

      <Card>
        <h3 className="mb-4 text-lg font-semibold">File Format</h3>
        <div>
          <Label htmlFor="format-select" className="mb-2 block">
            Import Format
          </Label>
          <Select
            id="format-select"
            value={format}
            onChange={(e) => setFormat(e.target.value as ImportFormat)}
          >
            <option value="auto">Auto-detect from file</option>
            <option value="skos">SKOS (Turtle, N3)</option>
            <option value="owl">OWL (RDF/XML)</option>
            <option value="graphml">GraphML</option>
          </Select>
          {format !== "auto" && (
            <p className="mt-2 text-sm text-gray-500">
              Format manually set to {format.toUpperCase()}
            </p>
          )}
        </div>
      </Card>

      <div className="flex gap-3">
        <Button
          data-testid="interchange-import-preview-button"
          onClick={handlePreview}
          color="blue"
          disabled={!selectedFile}
        >
          Preview Import (Dry Run)
        </Button>
      </div>
    </div>
  );
}

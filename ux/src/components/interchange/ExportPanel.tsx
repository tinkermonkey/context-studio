/**
 * Export Panel
 *
 * Form for exporting ontology data in various formats
 */

import React from "react";
import { Button, Card, Label, Select } from "flowbite-react";
import { Download } from "lucide-react";
import { useInterchangeExport } from "@/api/hooks/interchange";
import { SerializationScope } from "@/api/types/interchange";
import { useTaxonomies } from "@/api/hooks/taxonomies";
import { useConceptSchemes } from "@/api/hooks/conceptSchemes";
import { Taxonomy, ConceptScheme } from "@/api/types/ontology";
import { useButterToast } from "@/hooks/useButterToast";

type ExportFormat = "skos" | "owl" | "graphml";
type ScopeType = "whole_graph" | "taxonomy" | "scheme" | "entity_set";

export function ExportPanel() {
  const { success, error } = useButterToast();
  const [format, setFormat] = React.useState<ExportFormat>("skos");
  const [scopeType, setScopeType] = React.useState<ScopeType>("whole_graph");
  const [selectedTaxonomy, setSelectedTaxonomy] = React.useState<string>("");
  const [selectedScheme, setSelectedScheme] = React.useState<string>("");

  const { data: taxonomiesResponse } = useTaxonomies();
  const { data: schemesResponse } = useConceptSchemes();

  const taxonomies = Array.isArray(taxonomiesResponse)
    ? taxonomiesResponse
    : [];
  const schemes = Array.isArray(schemesResponse) ? schemesResponse : [];

  const exportMutation = useInterchangeExport({
    onSuccess: (blob) => {
      // Trigger browser download
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `export-${new Date().toISOString().split("T")[0]}.${format.toLowerCase()}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      success("Export downloaded successfully");
    },
    onError: (err) => {
      error(
        `Export failed: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    },
  });

  const buildScope = (): SerializationScope => {
    const baseScope = { scope_type: scopeType } as SerializationScope;

    switch (scopeType) {
      case "taxonomy":
        return {
          ...baseScope,
          taxonomy_id: selectedTaxonomy,
          include_descendants: true,
        };
      case "scheme":
        return {
          ...baseScope,
          scheme_id: selectedScheme,
          include_descendants: true,
        };
      case "whole_graph":
      default:
        return baseScope;
    }
  };

  const handleExport = () => {
    if (scopeType === "taxonomy" && !selectedTaxonomy) {
      error("Please select a taxonomy");
      return;
    }
    if (scopeType === "scheme" && !selectedScheme) {
      error("Please select a concept scheme");
      return;
    }

    exportMutation.mutate({
      format,
      scope: buildScope(),
    });
  };

  return (
    <div data-testid="interchange-export-panel" className="space-y-6">
      <Card>
        <h3 className="mb-4 text-lg font-semibold">Export Format</h3>
        <div>
          <Label htmlFor="format-select" className="mb-2 block">
            Select Format
          </Label>
          <Select
            id="format-select"
            data-testid="interchange-export-format-select"
            value={format}
            onChange={(e) => setFormat(e.target.value as ExportFormat)}
          >
            <option value="skos">
              SKOS (Simple Knowledge Organization System)
            </option>
            <option value="owl">OWL (Web Ontology Language)</option>
            <option value="graphml">GraphML (Graph Markup Language)</option>
          </Select>
        </div>
      </Card>

      <Card>
        <h3 className="mb-4 text-lg font-semibold">Export Scope</h3>
        <div>
          <Label htmlFor="scope-picker" className="mb-2 block">
            What to Export
          </Label>
          <Select
            id="scope-picker"
            data-testid="interchange-export-scope-picker"
            value={scopeType}
            onChange={(e) => setScopeType(e.target.value as ScopeType)}
          >
            <option value="whole_graph">Entire Graph</option>
            <option value="taxonomy">Specific Taxonomy</option>
            <option value="scheme">Specific Concept Scheme</option>
          </Select>
        </div>

        {scopeType === "taxonomy" && (
          <div className="mt-4">
            <Label htmlFor="taxonomy-select" className="mb-2 block">
              Select Taxonomy
            </Label>
            <Select
              id="taxonomy-select"
              value={selectedTaxonomy}
              onChange={(e) => setSelectedTaxonomy(e.target.value)}
            >
              <option value="">-- Choose a taxonomy --</option>
              {taxonomies.map((tax: Taxonomy) => (
                <option key={tax.id} value={tax.id}>
                  {tax.title}
                </option>
              ))}
            </Select>
          </div>
        )}

        {scopeType === "scheme" && (
          <div className="mt-4">
            <Label htmlFor="scheme-select" className="mb-2 block">
              Select Concept Scheme
            </Label>
            <Select
              id="scheme-select"
              value={selectedScheme}
              onChange={(e) => setSelectedScheme(e.target.value)}
            >
              <option value="">-- Choose a concept scheme --</option>
              {schemes.map((scheme: ConceptScheme) => (
                <option key={scheme.id} value={scheme.id}>
                  {scheme.title}
                </option>
              ))}
            </Select>
          </div>
        )}
      </Card>

      <div className="flex gap-3">
        <Button
          data-testid="interchange-export-download-button"
          onClick={handleExport}
          disabled={exportMutation.isPending}
          color="blue"
        >
          <Download className="mr-2 h-4 w-4" />
          {exportMutation.isPending ? "Exporting..." : "Download Export"}
        </Button>
      </div>
    </div>
  );
}

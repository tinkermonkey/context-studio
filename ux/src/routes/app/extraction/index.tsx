import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useExtract, useNlpAnalysis, useEnrichFromReferences } from "@/api/hooks/extraction";
import { ExtractionInput } from "@/components/extraction/ExtractionInput";
import { ExtractionResultPanel } from "@/components/extraction/ExtractionResultPanel";
import { EntityReviewPanel } from "@/components/extraction/EntityReviewPanel";
import { COPY } from "./-copy";
import type { components } from "@/api/types";

type ExtractionResultSchema = components["schemas"]["ExtractionResultSchema"];
type EnrichFromReferencesRequest = components["schemas"]["EnrichFromReferencesRequest"];

export const Route = createFileRoute("/app/extraction")({
  component: ExtractionPage,
});

function ExtractionPage() {
  const [extractionResult, setExtractionResult] = useState<ExtractionResultSchema | null>(null);
  const [nlpResult, setNlpResult] = useState<ExtractionResultSchema | null>(null);
  const [enrichmentResult, setEnrichmentResult] = useState<ExtractionResultSchema | null>(null);

  const extractMutation = useExtract();
  const nlpMutation = useNlpAnalysis();
  const enrichMutation = useEnrichFromReferences();

  const handleExtract = async (text: string) => {
    setExtractionResult(null);
    setNlpResult(null);
    setEnrichmentResult(null);

    // Start extraction
    extractMutation.mutate(text, {
      onSuccess: (result) => {
        setExtractionResult(result);
        // Automatically run NLP analysis on the same text
        nlpMutation.mutate(text, {
          onSuccess: (nlpData) => {
            setNlpResult(nlpData);
            // Trigger enrichment if we have extraction results
            if (result?.extracted_entities && result.extracted_entities.length > 0) {
              const enrichmentRequest: EnrichFromReferencesRequest = {
                text,
                extracted_entities: result.extracted_entities,
              };
              enrichMutation.mutate(enrichmentRequest, {
                onSuccess: (enrichmentData) => {
                  setEnrichmentResult(enrichmentData);
                },
              });
            }
          },
        });
      },
    });
  };

  const getLayerEntities = (layerIndex: number) => {
    let result: ExtractionResultSchema | null = null;

    // Determine which result to use based on layer
    if (layerIndex === 0 || layerIndex === 1) {
      result = extractionResult;
    } else if (layerIndex === 2) {
      result = nlpResult;
    } else if (layerIndex === 3) {
      result = enrichmentResult;
    }

    if (!result?.extracted_entities) return [];
    return result.extracted_entities.filter((e) => e.source_layer === layerIndex);
  };

  const getLayerResult = (layerIndex: number) => {
    let result: ExtractionResultSchema | null = null;

    if (layerIndex === 0 || layerIndex === 1) {
      result = extractionResult;
    } else if (layerIndex === 2) {
      result = nlpResult;
    } else if (layerIndex === 3) {
      result = enrichmentResult;
    }

    if (!result?.layers_executed) return null;
    return result.layers_executed.find((l) => l.layer_number === layerIndex);
  };

  return (
    <div data-testid="extraction-page">
      <div className="page-head">
        <div>
          <h1>{COPY.PAGE_TITLE}</h1>
          <p className="subtitle">{COPY.PAGE_SUBTITLE}</p>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "380px 1fr",
          gap: "20px",
          minHeight: "calc(100vh - 180px)",
        }}
      >
        {/* Left column - Input */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", overflow: "hidden" }}>
          <ExtractionInput onExtract={handleExtract} isLoading={extractMutation.isPending} />
        </div>

        {/* Right column - Results panels */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", overflow: "auto" }}>
          {/* KG Context Panel */}
          <ExtractionResultPanel
            layer={
              getLayerResult(0) || {
                layer_number: 0,
                layer_name: COPY.KG_CONTEXT_LAYER,
                entities_found: 0,
                duration_ms: 0,
                success: false,
              }
            }
            layerIndex={0}
            entities={getLayerEntities(0)}
            isLoading={extractMutation.isPending}
            error={
              extractMutation.isError && extractMutation.error instanceof Error
                ? extractMutation.error.message
                : extractMutation.isError
                  ? "Unknown error occurred"
                  : null
            }
          />
          <EntityReviewPanel
            entities={getLayerEntities(0)}
            layerIndex={0}
            isLoading={extractMutation.isPending}
          />

          {/* LLM Extraction Panel */}
          <ExtractionResultPanel
            layer={
              getLayerResult(1) || {
                layer_number: 1,
                layer_name: COPY.LLM_EXTRACTION_LAYER,
                entities_found: 0,
                duration_ms: 0,
                success: false,
              }
            }
            layerIndex={1}
            entities={getLayerEntities(1)}
            isLoading={extractMutation.isPending}
            error={
              extractMutation.isError && extractMutation.error instanceof Error
                ? extractMutation.error.message
                : extractMutation.isError
                  ? "Unknown error occurred"
                  : null
            }
          />
          <EntityReviewPanel
            entities={getLayerEntities(1)}
            layerIndex={1}
            isLoading={extractMutation.isPending}
          />

          {/* NLP Gap Fill Panel */}
          <ExtractionResultPanel
            layer={
              getLayerResult(2) || {
                layer_number: 2,
                layer_name: COPY.NLP_GAP_FILL_LAYER,
                entities_found: 0,
                duration_ms: 0,
                success: false,
              }
            }
            layerIndex={2}
            entities={getLayerEntities(2)}
            isLoading={nlpMutation.isPending}
            error={
              nlpMutation.isError && nlpMutation.error instanceof Error
                ? nlpMutation.error.message
                : nlpMutation.isError
                  ? "Unknown error occurred"
                  : null
            }
          />
          <EntityReviewPanel
            entities={getLayerEntities(2)}
            layerIndex={2}
            isLoading={nlpMutation.isPending}
          />

          {/* Reference Enrichment Panel */}
          <ExtractionResultPanel
            layer={
              getLayerResult(3) || {
                layer_number: 3,
                layer_name: COPY.REFERENCE_ENRICHMENT_LAYER,
                entities_found: 0,
                duration_ms: 0,
                success: false,
              }
            }
            layerIndex={3}
            entities={getLayerEntities(3)}
            isLoading={enrichMutation.isPending}
            error={
              enrichMutation.isError && enrichMutation.error instanceof Error
                ? enrichMutation.error.message
                : enrichMutation.isError
                  ? "Unknown error occurred"
                  : null
            }
          />
          <EntityReviewPanel
            entities={getLayerEntities(3)}
            layerIndex={3}
            isLoading={enrichMutation.isPending}
          />
        </div>
      </div>
    </div>
  );
}

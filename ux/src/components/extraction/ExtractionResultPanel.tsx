import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Panel } from "@/components/ui/Panel";
import { Chip } from "@/components/ui/Chip";
import { formatConfidence } from "@/utils/formatters";
import { COPY } from "@/routes/app/extraction/-copy";
import type { components } from "@/api/types";

type ExtractionLayerResultSchema = components["schemas"]["ExtractionLayerResultSchema"];

interface ExtractionResultPanelProps {
  layer: ExtractionLayerResultSchema;
  layerIndex: number;
  entities: Array<{
    id: string;
    label: string;
    entity_type: string;
    confidence: number;
  }>;
  isLoading?: boolean;
  error?: string | null;
}

export function ExtractionResultPanel({
  layer,
  layerIndex,
  entities,
  isLoading = false,
  error = null,
}: ExtractionResultPanelProps) {
  const [showRawJson, setShowRawJson] = useState(false);

  const layerNames: Record<number, string> = {
    0: "KG Context",
    1: "LLM Extraction",
    2: "NLP Gap Fill",
    3: "Reference Enrichment",
  };

  const layerName = layerNames[layerIndex] || `Layer ${layerIndex}`;
  const testId = `extraction-panel-${layerName.toLowerCase().replace(/ /g, "-")}`;

  const renderContent = () => {
    if (isLoading) {
      return <div style={{ padding: "12px", color: "var(--canvas-fg-2)" }}>{COPY.LOADING_STATE}</div>;
    }

    if (error) {
      return (
        <div style={{ padding: "12px", color: "var(--rose-600)" }}>
          <span>Error: {error}</span>
        </div>
      );
    }

    if (entities.length === 0) {
      return (
        <div style={{ padding: "12px", color: "var(--canvas-fg-2)" }}>{COPY.NO_ENTITIES_EXTRACTED}</div>
      );
    }

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div>
          <div
            style={{ marginBottom: "8px", fontSize: "var(--text-sm)", color: "var(--canvas-fg-2)" }}
          >
            {COPY.ENTITIES_LABEL} ({entities.length})
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {entities.map((entity) => (
              <div key={entity.id} title={`Type: ${entity.entity_type}`}>
                <Chip color="cyan">
                  {entity.label} ({formatConfidence(entity.confidence)})
                </Chip>
              </div>
            ))}
          </div>
        </div>

        {showRawJson && (
          <div
            style={{
              backgroundColor: "var(--canvas-bg-2)",
              padding: "12px",
              borderRadius: "4px",
              fontSize: "var(--text-xs)",
              overflow: "auto",
              maxHeight: "200px",
            }}
          >
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {JSON.stringify(
                {
                  layer,
                  entities,
                },
                null,
                2,
              )}
            </pre>
          </div>
        )}
      </div>
    );
  };

  const toggleActions = (
    <button
      type="button"
      className="btn btn-icon"
      onClick={() => setShowRawJson(!showRawJson)}
      style={{ padding: "4px", display: "flex", alignItems: "center" }}
      title={showRawJson ? COPY.HIDE_RAW_JSON : COPY.SHOW_RAW_JSON}
      aria-expanded={showRawJson}
      aria-controls={`${testId}-json`}
    >
      <ChevronDown
        size={16}
        style={{
          transform: showRawJson ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform 200ms",
        }}
      />
    </button>
  );

  return (
    <div data-testid={testId}>
      <Panel title={layerName} actions={toggleActions}>
        <div id={`${testId}-json`}>{renderContent()}</div>
      </Panel>
    </div>
  );
}

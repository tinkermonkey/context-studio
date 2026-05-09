import type { components } from "@/api/types";
import { Cpu, Play } from "lucide-react";

type PipelineConfigurationResponse =
  components["schemas"]["PipelineConfigurationResponse"];

interface PipelineCardProps {
  pipeline: PipelineConfigurationResponse;
  onExecute?: (id: string) => void;
}

export function PipelineCard({ pipeline, onExecute }: PipelineCardProps) {
  return (
    <div
      className="pipeline-card"
      style={{
        background: "var(--canvas-card)",
        border: "1px solid var(--canvas-bd)",
        borderRadius: "var(--radius-lg, 10px)",
        padding: "var(--space-4)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-2)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <Cpu size={16} style={{ color: "var(--accent-violet, #7c3aed)", flexShrink: 0 }} />
        <span
          style={{
            fontSize: "var(--text-sm)",
            fontWeight: 600,
            color: "var(--canvas-fg)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {pipeline.title}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          fontSize: "var(--text-xs)",
          color: "var(--canvas-fg-3)",
          fontFamily: "var(--mono)",
        }}
      >
        <span>{pipeline.provider}</span>
        <span>·</span>
        <span>{pipeline.model}</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "var(--space-1)" }}>
        <span
          style={{
            fontSize: "var(--text-xs)",
            padding: "2px 8px",
            borderRadius: "999px",
            background: pipeline.enabled
              ? "color-mix(in oklab, var(--accent-emerald, #10b981) 15%, transparent)"
              : "var(--canvas-bd)",
            color: pipeline.enabled ? "var(--accent-emerald, #10b981)" : "var(--canvas-fg-3)",
            border: `1px solid ${pipeline.enabled ? "color-mix(in oklab, var(--accent-emerald, #10b981) 30%, transparent)" : "var(--canvas-bd-2)"}`,
          }}
        >
          {pipeline.enabled ? "enabled" : "disabled"}
        </span>

        {pipeline.enabled && onExecute && (
          <button
            type="button"
            onClick={() => onExecute(pipeline.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: "var(--text-xs)",
              padding: "3px 10px",
              borderRadius: "var(--radius-md, 6px)",
              background: "var(--canvas-bd)",
              color: "var(--canvas-fg)",
              border: "1px solid var(--canvas-bd-2)",
              cursor: "pointer",
            }}
          >
            <Play size={10} />
            Run
          </button>
        )}
      </div>
    </div>
  );
}

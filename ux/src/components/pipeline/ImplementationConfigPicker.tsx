import { Field } from "@tinkermonkey/heimdall-ui";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";

export interface ImplementationConfigPickerProps {
  pipelineType: string;
  onSelectImplementation: (id: string) => void;
  onSelectConfig: (ref: string, version?: number) => void;
  selectedImplementationId?: string;
  selectedConfigRef?: string;
  disabled?: boolean;
  implementationError?: string;
  configError?: string;
}

export function ImplementationConfigPicker({
  pipelineType,
  onSelectImplementation,
  onSelectConfig,
  selectedImplementationId,
  selectedConfigRef,
  disabled = false,
  implementationError,
  configError,
}: ImplementationConfigPickerProps) {
  const { data: implementations, isLoading: implLoading } =
    usePipelineImplementations(pipelineType);

  const { data: configurations, isLoading: configLoading } =
    usePipelineConfigurations(pipelineType, selectedImplementationId || "");

  return (
    <>
      <Field
        label="Implementation"
        required
        error={implementationError}
        errorId="implementation-error"
      >
        <select
          value={selectedImplementationId || ""}
          onChange={(e) => {
            onSelectImplementation(e.target.value);
            onSelectConfig("", undefined);
          }}
          disabled={disabled || implLoading}
          aria-invalid={!!implementationError}
          aria-describedby={
            implementationError ? "implementation-error" : undefined
          }
          data-testid="implementation-select"
          style={{
            width: "100%",
            padding: "8px 12px",
            borderRadius: "4px",
            border: "1px solid rgb(var(--canvas-fg-4))",
            backgroundColor: "rgb(var(--canvas-bg))",
            fontSize: "var(--text-sm)",
            fontFamily: "inherit",
            color: "rgb(var(--canvas-fg-1))",
          }}
        >
          <option value="">Choose implementation…</option>
          {implementations?.map((impl) => (
            <option key={impl.id} value={impl.id}>
              {impl.id}
            </option>
          ))}
        </select>
      </Field>

      {selectedImplementationId && (
        <Field
          label="Configuration"
          required
          error={configError}
          errorId="configuration-error"
        >
          <select
            value={selectedConfigRef || ""}
            onChange={(e) => {
              if (!e.target.value) {
                onSelectConfig("", undefined);
                return;
              }
              const parts = e.target.value.split("_v");
              const configRef = parts[0];
              const version = parts[1] ? parseInt(parts[1], 10) : undefined;
              onSelectConfig(configRef, version);
            }}
            disabled={disabled || configLoading || !configurations?.length}
            aria-invalid={!!configError}
            aria-describedby={configError ? "configuration-error" : undefined}
            data-testid="configuration-select"
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "4px",
              border: "1px solid rgb(var(--canvas-fg-4))",
              backgroundColor: "rgb(var(--canvas-bg))",
              fontSize: "var(--text-sm)",
              fontFamily: "inherit",
              color: "rgb(var(--canvas-fg-1))",
            }}
          >
            <option value="">Choose configuration…</option>
            {configurations?.map((config) => (
              <option
                key={`${config.config_ref}_v${config.version}`}
                value={`${config.config_ref}_v${config.version}`}
              >
                {config.config_ref} v{config.version}
              </option>
            ))}
          </select>
        </Field>
      )}
    </>
  );
}

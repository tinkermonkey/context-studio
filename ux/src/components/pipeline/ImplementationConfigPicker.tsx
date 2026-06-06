import { Field } from "@tinkermonkey/heimdall-ui";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";

export interface ImplementationConfigPickerProps {
  pipelineType: string;
  onSelectImplementation: (id: string) => void;
  onSelectConfig: (compositeValue: string) => void;
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
            onSelectConfig("");
          }}
          disabled={disabled || implLoading}
          aria-invalid={!!implementationError}
          aria-describedby={
            implementationError ? "implementation-error" : undefined
          }
          data-testid="implementation-select"
          className="wizard-select"
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
            value={selectedConfigRef}
            onChange={(e) => onSelectConfig(e.target.value)}
            disabled={disabled || configLoading || !configurations?.length}
            aria-invalid={!!configError}
            aria-describedby={configError ? "configuration-error" : undefined}
            data-testid="configuration-select"
            className="wizard-select"
          >
            <option value="">Choose configuration…</option>
            {configurations?.map((config) => {
              const compositeValue = `${config.config_ref}_v${config.version}`;
              return (
                <option
                  key={compositeValue}
                  value={compositeValue}
                >
                  {config.config_ref} v{config.version}
                </option>
              );
            })}
          </select>
        </Field>
      )}
    </>
  );
}

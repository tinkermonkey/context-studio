import { Field } from "@tinkermonkey/heimdall-ui";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";

export interface ConfigSelection {
  configRef: string;
  version: number;
}

export const encodeConfigSelection = (configRef: string, version: number): string => {
  return btoa(JSON.stringify({ configRef, version }));
};

export const decodeConfigSelection = (encoded: string): ConfigSelection => {
  if (!encoded) {
    throw new Error("Configuration selection is missing");
  }

  let decoded: unknown;
  try {
    decoded = JSON.parse(atob(encoded));
  } catch {
    throw new Error("Invalid configuration selection format");
  }

  if (!decoded || typeof decoded !== "object") {
    throw new Error("Invalid configuration selection format");
  }

  const config = decoded as Record<string, unknown>;
  if (typeof config.configRef !== "string" || typeof config.version !== "number") {
    throw new Error("Invalid configuration selection format");
  }

  return { configRef: config.configRef, version: config.version };
};

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
  const {
    data: implementations,
    isLoading: implLoading,
    isError: implError,
    error: implErrorObj,
  } = usePipelineImplementations(pipelineType);

  const {
    data: configurations,
    isLoading: configLoading,
    isError: configQueryError,
    error: configErrorObj,
  } = usePipelineConfigurations(pipelineType, selectedImplementationId || "");

  const implErrorMessage = implError
    ? implErrorObj instanceof Error
      ? implErrorObj.message
      : "Failed to load implementations"
    : implementationError;

  const configErrorMessage = configQueryError
    ? configErrorObj instanceof Error
      ? configErrorObj.message
      : "Failed to load configurations"
    : configError;

  return (
    <div data-testid="implementation-config-picker">
      <Field
        label="Implementation"
        required
        error={implErrorMessage}
        errorId="implementation-error"
      >
        <select
          value={selectedImplementationId || ""}
          onChange={(e) => {
            onSelectImplementation(e.target.value);
            onSelectConfig("");
          }}
          disabled={disabled || implLoading || implError}
          aria-invalid={!!implErrorMessage}
          aria-describedby={implErrorMessage ? "implementation-error" : undefined}
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
          error={configErrorMessage}
          errorId="configuration-error"
        >
          <select
            value={selectedConfigRef}
            onChange={(e) => onSelectConfig(e.target.value)}
            disabled={disabled || configLoading || configQueryError || !configurations?.length}
            aria-invalid={!!configErrorMessage}
            aria-describedby={configErrorMessage ? "configuration-error" : undefined}
            data-testid="configuration-select"
            className="wizard-select"
          >
            <option value="">Choose configuration…</option>
            {configurations?.map((config) => {
              const compositeValue = encodeConfigSelection(config.config_ref, config.version);
              return (
                <option key={compositeValue} value={compositeValue}>
                  {config.config_ref} v{config.version}
                </option>
              );
            })}
          </select>
        </Field>
      )}
    </div>
  );
}

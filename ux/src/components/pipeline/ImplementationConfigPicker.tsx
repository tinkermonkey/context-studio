import { Field, Select } from "@tinkermonkey/heimdall-ui";
import type { DropdownPlacement } from "@tinkermonkey/heimdall-ui";
import type { PipelineSelection } from "@/hooks/usePipelineSelection";
import "./ImplementationConfigPicker.css";

export interface ImplementationConfigPickerProps {
  /** The selection to show and change (usePipelineSelection). */
  selection: PipelineSelection;
  /** Prefix of the picker's ids and test ids; unique per picker on a page. */
  idPrefix: string;
  /** Names the run being selected for, where a page starts more than one. */
  legend?: string;
  disabled?: boolean;
  /**
   * Where the option lists open. They are not portaled, so a picker at the
   * bottom of a Panel (which clips its content) opens upwards.
   */
  placement?: DropdownPlacement;
  /** Called after either choice changes, e.g. to clear a start error. */
  onChange?: () => void;
}

const SERVER_DEFAULT = "Server default";

/**
 * The one picker for what a pipeline run is selected by: an implementation,
 * then a configuration of that implementation. Options and preselection are
 * the API's; nothing selected means the server's default applies.
 */
export function ImplementationConfigPicker({
  selection,
  idPrefix,
  legend,
  disabled = false,
  placement,
  onChange,
}: ImplementationConfigPickerProps) {
  const { implementations, configurations, implementation, configuration } = selection;
  const implementationId = `${idPrefix}-implementation`;
  const configurationId = `${idPrefix}-configuration`;
  const implementationErrorId = `${implementationId}-error`;
  const configurationErrorId = `${configurationId}-error`;
  const named = (label: string) => (legend ? `${legend}: ${label.toLowerCase()}` : label);
  // Heimdall's Select takes no aria-describedby, so the group points at its load errors.
  const describedBy = [
    selection.implementationsError && implementationErrorId,
    selection.configurationsError && configurationErrorId,
  ]
    .filter(Boolean)
    .join(" ");
  const model = [configuration?.provider, configuration?.model].filter(Boolean).join(" · ");

  return (
    <fieldset
      className="impl-config-picker"
      aria-label={legend ? undefined : "Implementation and configuration"}
      aria-describedby={describedBy || undefined}
      data-testid={`${idPrefix}-picker`}
    >
      {legend && <legend className="impl-config-picker__legend">{legend}</legend>}
      <div className="impl-config-picker__fields">
        <Field
          label="Implementation"
          htmlFor={implementationId}
          error={selection.implementationsError}
          errorId={implementationErrorId}
        >
          <Select
            id={implementationId}
            value={implementation?.id ?? ""}
            onChange={(id) => {
              selection.selectImplementation(id);
              onChange?.();
            }}
            placeholder={SERVER_DEFAULT}
            placement={placement}
            ariaLabel={named("Implementation")}
            disabled={disabled || implementations.length === 0}
            error={!!selection.implementationsError}
            data-testid={implementationId}
          >
            {implementations.map((i) => (
              <Select.Item
                key={i.id}
                value={i.id}
                description={i.is_default ? "Default implementation" : undefined}
              >
                {i.id}
              </Select.Item>
            ))}
          </Select>
        </Field>

        <Field
          label="Configuration"
          htmlFor={configurationId}
          error={selection.configurationsError}
          errorId={configurationErrorId}
        >
          <Select
            id={configurationId}
            value={configuration?.config_ref ?? ""}
            onChange={(configRef) => {
              selection.selectConfiguration(configRef);
              onChange?.();
            }}
            placeholder={SERVER_DEFAULT}
            placement={placement}
            ariaLabel={named("Configuration")}
            disabled={disabled || configurations.length === 0}
            error={!!selection.configurationsError}
            data-testid={configurationId}
          >
            {configurations.map((c) => (
              <Select.Item
                key={c.id}
                value={c.config_ref}
                description={
                  [c.provider, c.model, c.is_default ? "default configuration" : null]
                    .filter(Boolean)
                    .join(" · ") || undefined
                }
              >
                {c.config_ref}
              </Select.Item>
            ))}
          </Select>
        </Field>
      </div>
      {model && (
        <span className="impl-config-picker__model" data-testid={`${idPrefix}-configuration-model`}>
          {model}
        </span>
      )}
    </fieldset>
  );
}

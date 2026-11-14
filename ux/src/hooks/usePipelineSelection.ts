import { useState } from "react";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";
import type { PipelineConfiguration, PipelineImplementation } from "@/api/services/pipeline";

export interface PipelineSelectionOptions {
  /** Offer only the implementations this accepts, e.g. those that can extract a source. */
  offers?: (implementation: PipelineImplementation) => boolean;
}

/**
 * What a run of one pipeline type is selected by: an implementation, then one
 * of that implementation's configurations. Read by ImplementationConfigPicker.
 */
export interface PipelineSelection {
  pipelineType: string;
  /** The implementations offered. */
  implementations: PipelineImplementation[];
  /** The enabled configurations of the selected implementation. */
  configurations: PipelineConfiguration[];
  /** Undefined until the list loads, or when the default is not among those offered. */
  implementation?: PipelineImplementation;
  configuration?: PipelineConfiguration;
  selectImplementation: (id: string) => void;
  selectConfiguration: (configRef: string) => void;
  implementationsError?: string;
  configurationsError?: string;
}

const message = (error: unknown, fallback: string) =>
  error instanceof Error && error.message ? error.message : fallback;

/**
 * The selection for a run of `pipelineType`. Until the user chooses, it is the
 * server's: the implementation and the configuration the API marks `is_default`.
 * A disabled configuration is never offered or selected.
 */
export function usePipelineSelection(
  pipelineType: string,
  { offers }: PipelineSelectionOptions = {},
): PipelineSelection {
  const [implementationChoice, setImplementationChoice] = useState<string>();
  const [configurationChoice, setConfigurationChoice] = useState<string>();

  const implementationsQuery = usePipelineImplementations(pipelineType);
  const implementations = (implementationsQuery.data ?? []).filter((i) => !offers || offers(i));
  const implementation =
    implementations.find((i) => i.id === implementationChoice) ??
    implementations.find((i) => i.is_default);

  const configurationsQuery = usePipelineConfigurations(pipelineType, implementation?.id ?? "");
  const configurations = (configurationsQuery.data ?? []).filter((c) => c.enabled !== false);
  const configuration =
    configurations.find((c) => c.config_ref === configurationChoice) ??
    configurations.find((c) => c.is_default);

  return {
    pipelineType,
    implementations,
    configurations,
    implementation,
    configuration,
    selectImplementation: (id) => {
      setImplementationChoice(id);
      // A configuration belongs to one implementation.
      setConfigurationChoice(undefined);
    },
    selectConfiguration: setConfigurationChoice,
    implementationsError: implementationsQuery.isError
      ? message(implementationsQuery.error, "Failed to load implementations")
      : undefined,
    configurationsError: configurationsQuery.isError
      ? message(configurationsQuery.error, "Failed to load configurations")
      : undefined,
  };
}

/**
 * The run-request fields of a selection. A part that is not selected is left
 * out, so the server's default applies; the model is the configuration's and
 * is never sent.
 */
export function selectionRequestFields(
  selection: Pick<PipelineSelection, "implementation" | "configuration">,
): { implementation_id?: string; configuration_ref?: string } {
  return {
    ...(selection.implementation ? { implementation_id: selection.implementation.id } : {}),
    ...(selection.configuration ? { configuration_ref: selection.configuration.config_ref } : {}),
  };
}

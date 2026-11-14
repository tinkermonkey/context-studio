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
  /** Undefined only until the list loads, or when nothing is offered. */
  implementation?: PipelineImplementation;
  /** Undefined only until the list loads, or when the implementation has no enabled configuration. */
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
 * A disabled configuration is never offered or selected. Where the default is
 * not among those offered (the default implementation filtered out, or a
 * disabled default configuration) the first offered one is selected instead,
 * so the request always names what the picker shows: the server refuses a run
 * that leaves such a choice to it.
 */
export function usePipelineSelection(
  pipelineType: string,
  { offers }: PipelineSelectionOptions = {},
): PipelineSelection {
  const [implementationChoice, setImplementationChoice] = useState<string>();
  // A config_ref is unique within one implementation only, so the choice
  // names the implementation it was made for and holds for no other.
  const [configurationChoice, setConfigurationChoice] = useState<{
    implementationId: string;
    configRef: string;
  }>();

  const implementationsQuery = usePipelineImplementations(pipelineType);
  const implementations = (implementationsQuery.data ?? []).filter((i) => !offers || offers(i));
  const implementation =
    implementations.find((i) => i.id === implementationChoice) ??
    implementations.find((i) => i.is_default) ??
    implementations[0];

  const configurationsQuery = usePipelineConfigurations(pipelineType, implementation?.id ?? "");
  const configurations = (configurationsQuery.data ?? []).filter((c) => c.enabled !== false);
  const chosenRef =
    configurationChoice?.implementationId === implementation?.id
      ? configurationChoice?.configRef
      : undefined;
  const configuration =
    configurations.find((c) => c.config_ref === chosenRef) ??
    configurations.find((c) => c.is_default) ??
    configurations[0];

  return {
    pipelineType,
    implementations,
    configurations,
    implementation,
    configuration,
    selectImplementation: setImplementationChoice,
    selectConfiguration: (configRef) => {
      if (implementation)
        setConfigurationChoice({ implementationId: implementation.id, configRef });
    },
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

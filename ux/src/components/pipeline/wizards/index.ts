import type { ComponentType } from "react";
import { SchemaExtractionWizard } from "./SchemaExtractionWizard";
import { IndividualExtractionWizard } from "./IndividualExtractionWizard";
import { SchemaGroundingWizard } from "./SchemaGroundingWizard";
import { DefinitionRefinementWizard } from "./DefinitionRefinementWizard";
import { ConnectionRefinementWizard } from "./ConnectionRefinementWizard";

/** The run wizard of each pipeline type that has one (/app/pipelines/types/$type/run). */
export const RUN_WIZARDS: Record<string, ComponentType> = {
  schema_extraction: SchemaExtractionWizard,
  individual_extraction: IndividualExtractionWizard,
  schema_node_grounding: SchemaGroundingWizard,
  schema_node_definition_refinement: DefinitionRefinementWizard,
  schema_node_connection_refinement: ConnectionRefinementWizard,
};

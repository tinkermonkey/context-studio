/**
 * Test helper utilities for E2E tests.
 */

/**
 * Export factory functions for convenient access
 */
export {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
  createRelationship,
  createIndividual,
  getIndividualsByClass,
  clearTestData,
  type Taxonomy,
  type ConceptScheme,
  type OntologyClass,
  type PropertyDefinition,
  type Relationship,
  type Individual,
} from "./factories";

/**
 * Test fixtures for OntologyService using OpenAPI-generated types.
 * All fixtures are typed against components["schemas"] from ux/src/api/types/index.ts
 */

import type { components } from "@/api/types";

// ============================================================================
// Taxonomy Fixtures
// ============================================================================

export function createTaxonomy(
  overrides?: Partial<components["schemas"]["TaxonomyResponse"]>,
): components["schemas"]["TaxonomyResponse"] {
  return {
    id: "tax-123",
    title: "Test Taxonomy",
    description: "A test taxonomy for unit testing",
    created_at: new Date().toISOString(),
    last_modified: new Date().toISOString(),
    version: 1,
    status: "draft",
    ...overrides,
  };
}

export function createListTaxonomies(
  items?: components["schemas"]["TaxonomyResponse"][],
): components["schemas"]["ListResponse_TaxonomyResponse_"] {
  return {
    items: items || [createTaxonomy()],
    total: items?.length ?? 1,
    limit: 10,
    offset: 0,
  };
}

export function createTaxonomyCreateRequest(
  overrides?: Partial<components["schemas"]["TaxonomyCreateRequest"]>,
): components["schemas"]["TaxonomyCreateRequest"] {
  return {
    title: "New Taxonomy",
    description: "A new test taxonomy",
    ...overrides,
  };
}

// ============================================================================
// Concept Scheme Fixtures
// ============================================================================

export function createConceptScheme(
  overrides?: Partial<components["schemas"]["ConceptSchemeResponse"]>,
): components["schemas"]["ConceptSchemeResponse"] {
  return {
    id: "scheme-123",
    title: "Test Scheme",
    description: "A test concept scheme",
    taxonomy_id: "tax-123",
    created_at: new Date().toISOString(),
    last_modified: new Date().toISOString(),
    version: 1,
    status: "draft",
    ...overrides,
  };
}

export function createListSchemes(
  items?: components["schemas"]["ConceptSchemeResponse"][],
): components["schemas"]["ListResponse_ConceptSchemeResponse_"] {
  return {
    items: items || [createConceptScheme()],
    total: items?.length ?? 1,
    limit: 10,
    offset: 0,
  };
}

export function createConceptSchemeCreateRequest(
  overrides?: Partial<components["schemas"]["ConceptSchemeCreateRequest"]>,
): components["schemas"]["ConceptSchemeCreateRequest"] {
  return {
    title: "New Scheme",
    description: "A new test scheme",
    ...overrides,
  };
}

// ============================================================================
// Class Fixtures
// ============================================================================

export function createClass(
  overrides?: Partial<components["schemas"]["ClassResponse"]>,
): components["schemas"]["ClassResponse"] {
  return {
    id: "class-123",
    title: "Test Class",
    description: "A test class",
    concept_scheme_id: "scheme-123",
    taxonomy_id: "tax-123",
    parent_class_id: null,
    created_at: new Date().toISOString(),
    last_modified: new Date().toISOString(),
    version: 1,
    status: "draft",
    ...overrides,
  };
}

export function createListClasses(
  items?: components["schemas"]["ClassResponse"][],
): components["schemas"]["ListResponse_ClassResponse_"] {
  return {
    items: items || [createClass()],
    total: items?.length ?? 1,
    limit: 10,
    offset: 0,
  };
}

export function createClassCreateRequest(
  overrides?: Partial<components["schemas"]["ClassCreateRequest"]>,
): components["schemas"]["ClassCreateRequest"] {
  return {
    title: "New Class",
    description: "A new test class",
    ...overrides,
  };
}

// ============================================================================
// Individual Fixtures
// ============================================================================

export function createIndividual(
  overrides?: Partial<components["schemas"]["IndividualResponse"]>,
): components["schemas"]["IndividualResponse"] {
  return {
    id: "ind-123",
    title: "Test Individual",
    description: "A test individual",
    class_ids: ["class-123"],
    version: 1,
    status: "draft",
    ...overrides,
  };
}

export function createListIndividuals(
  items?: components["schemas"]["IndividualResponse"][],
): components["schemas"]["ListResponse_IndividualResponse_"] {
  return {
    items: items || [createIndividual()],
    total: items?.length ?? 1,
    limit: 10,
    offset: 0,
  };
}

export function createIndividualCreateRequest(
  overrides?: Partial<components["schemas"]["IndividualCreateRequest"]>,
): components["schemas"]["IndividualCreateRequest"] {
  return {
    title: "New Individual",
    description: "A new test individual",
    class_ids: ["class-123"],
    ...overrides,
  };
}

// ============================================================================
// Property Definition Fixtures
// ============================================================================

export function createPropertyDefinition(
  overrides?: Partial<components["schemas"]["PropertyDefinitionResponse"]>,
): components["schemas"]["PropertyDefinitionResponse"] {
  return {
    id: "prop-123",
    identifier: "test_property",
    title: "Test Property",
    description: "A test property definition",
    created_at: new Date().toISOString(),
    last_modified: new Date().toISOString(),
    version: 1,
    status: "draft",
    ...overrides,
  };
}

export function createListProperties(
  items?: components["schemas"]["PropertyDefinitionResponse"][],
): components["schemas"]["ListResponse_PropertyDefinitionResponse_"] {
  return {
    items: items || [createPropertyDefinition()],
    total: items?.length ?? 1,
    limit: 10,
    offset: 0,
  };
}

export function createPropertyDefinitionCreateRequest(
  overrides?: Partial<components["schemas"]["PropertyDefinitionCreateRequest"]>,
): components["schemas"]["PropertyDefinitionCreateRequest"] {
  return {
    identifier: "new_property",
    title: "New Property",
    description: "A new test property",
    ...overrides,
  };
}

// ============================================================================
// Relationship Fixtures
// ============================================================================

export function createRelationship(
  overrides?: Partial<components["schemas"]["RelationshipResponse"]>,
): components["schemas"]["RelationshipResponse"] {
  return {
    id: "rel-123",
    source_id: "class-123",
    target_id: "class-456",
    property_definition_id: "prop-123",
    ...overrides,
  };
}

export function createListRelationships(
  items?: components["schemas"]["RelationshipResponse"][],
): components["schemas"]["ListResponse_RelationshipResponse_"] {
  return {
    items: items || [createRelationship()],
    total: items?.length ?? 1,
    limit: 10,
    offset: 0,
  };
}

export function createRelationshipCreateRequest(
  overrides?: Partial<components["schemas"]["RelationshipCreateRequest"]>,
): components["schemas"]["RelationshipCreateRequest"] {
  return {
    source_id: "class-123",
    target_id: "class-456",
    relationship_type: "related_to",
    ...overrides,
  };
}

// ============================================================================
// PublishDiffStats Fixture
// ============================================================================

export function createPublishDiffStats(
  overrides?: Partial<components["schemas"]["PublishDiffStats"]>,
): components["schemas"]["PublishDiffStats"] {
  return {
    added: 5,
    modified: 3,
    removed: 1,
    ...overrides,
  };
}

// ============================================================================
// DataPropertyValueResponse Fixture
// ============================================================================

export function createDataPropertyValue(
  overrides?: Partial<components["schemas"]["DataPropertyValueResponse"]>,
): components["schemas"]["DataPropertyValueResponse"] {
  return {
    property_identifier: "test_property",
    value: "test_value",
    ...overrides,
  };
}

export function createListDataPropertyValues(
  items?: components["schemas"]["DataPropertyValueResponse"][],
): components["schemas"]["ListResponse_DataPropertyValueResponse_"] {
  return {
    items: items || [createDataPropertyValue()],
    total: items?.length ?? 1,
    limit: 10,
    offset: 0,
  };
}

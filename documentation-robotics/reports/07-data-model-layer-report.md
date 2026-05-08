# Data Model

Data entities, relationships, and data structure definitions.

## Report Index

- [Layer Introduction](#layer-introduction)
- [Intra-Layer Relationships](#intra-layer-relationships)
- [Inter-Layer Dependencies](#inter-layer-dependencies)
- [Inter-Layer Relationships Table](#inter-layer-relationships-table)
- [Element Reference](#element-reference)

## Layer Introduction

| Metric                    | Count |
| ------------------------- | ----- |
| Elements                  | 18    |
| Intra-Layer Relationships | 12    |
| Inter-Layer Relationships | 12    |
| Inbound Relationships     | 0     |
| Outbound Relationships    | 12    |

**Cross-Layer References**:

- **Downstream layers**: [API](./06-api-layer-report.md), [Technology](./05-technology-layer-report.md)

## Intra-Layer Relationships

```mermaid
flowchart LR
  subgraph data_model
    data_model_arrayschema_external_references_list["external_references list"]
    data_model_numericschema_relationship_weight["relationship weight"]
    data_model_objectschema_change_event["Change Event"]
    data_model_objectschema_changeset["Changeset"]
    data_model_objectschema_changeset_event["Changeset Event"]
    data_model_objectschema_conflict_resolution["Conflict Resolution"]
    data_model_objectschema_entity_version["Entity Version"]
    data_model_objectschema_extraction_result["Extraction Result"]
    data_model_objectschema_import_run["Import Run"]
    data_model_objectschema_individual_class["Individual Class"]
    data_model_objectschema_ontology_entity["Ontology Entity"]
    data_model_objectschema_pipeline_configuration["Pipeline Configuration"]
    data_model_objectschema_pipeline_execution["Pipeline Execution"]
    data_model_objectschema_property_definition["Property Definition"]
    data_model_objectschema_proposal["Proposal"]
    data_model_objectschema_relationship["Relationship"]
    data_model_stringschema_iso_8601_datetime["ISO 8601 datetime"]
    data_model_stringschema_uuid_string["UUID string"]
    data_model_arrayschema_external_references_list -->|aggregates| data_model_numericschema_relationship_weight
    data_model_arrayschema_external_references_list -->|aggregates| data_model_objectschema_ontology_entity
    data_model_arrayschema_external_references_list -->|aggregates| data_model_stringschema_iso_8601_datetime
    data_model_arrayschema_external_references_list -->|aggregates| data_model_stringschema_uuid_string
    data_model_objectschema_change_event -->|extends| data_model_objectschema_ontology_entity
    data_model_objectschema_changeset -->|extends| data_model_objectschema_changeset_event
    data_model_objectschema_changeset -->|extends| data_model_objectschema_proposal
    data_model_objectschema_import_run -->|extends| data_model_objectschema_change_event
    data_model_objectschema_import_run -->|extends| data_model_objectschema_changeset
    data_model_objectschema_ontology_entity -->|extends| data_model_objectschema_relationship
    data_model_objectschema_pipeline_configuration -->|extends| data_model_objectschema_pipeline_execution
    data_model_objectschema_proposal -->|extends| data_model_objectschema_conflict_resolution
  end
```

## Inter-Layer Dependencies

```mermaid
flowchart TB
  classDef current fill:#f9f,stroke:#333,stroke-width:2px
  motivation["Motivation"]
  business["Business"]
  security["Security"]
  application["Application"]
  technology["Technology"]
  api["API"]
  data_model["Data Model"]
  data_store["Data Store"]
  ux["UX"]
  navigation["Navigation"]
  apm["APM"]
  testing["Testing"]
  data_model --> api
  data_model --> technology
  class data_model current
```

## Inter-Layer Relationships Table

| Relationship ID                                                | Source Node                                      | Dest Node                                            | Dest Layer   | Predicate    | Cardinality  | Strength |
| -------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------- | ------------ | ------------ | ------------ | -------- |
| `data-model.objectschema.depends-on.technology.systemsoftware` | `data-model.objectschema.change-event`           | `technology.systemsoftware.sqlalchemy`               | `technology` | `depends-on` | many-to-many | medium   |
| `data-model.objectschema.depends-on.technology.systemsoftware` | `data-model.objectschema.changeset`              | `technology.systemsoftware.sqlalchemy`               | `technology` | `depends-on` | many-to-many | medium   |
| `data-model.objectschema.maps-to.api.response`                 | `data-model.objectschema.entity-version`         | `api.response.entity-version-response`               | `api`        | `maps-to`    | many-to-many | medium   |
| `data-model.objectschema.maps-to.api.response`                 | `data-model.objectschema.extraction-result`      | `api.response.extraction-result-schema`              | `api`        | `maps-to`    | many-to-many | medium   |
| `data-model.objectschema.depends-on.technology.systemsoftware` | `data-model.objectschema.import-run`             | `technology.systemsoftware.sqlalchemy`               | `technology` | `depends-on` | many-to-many | medium   |
| `data-model.objectschema.maps-to.api.requestbody`              | `data-model.objectschema.individual-class`       | `api.requestbody.individual-class-list-request`      | `api`        | `maps-to`    | many-to-many | medium   |
| `data-model.objectschema.maps-to.api.requestbody`              | `data-model.objectschema.individual-class`       | `api.requestbody.individual-class-request`           | `api`        | `maps-to`    | many-to-many | medium   |
| `data-model.objectschema.depends-on.technology.systemsoftware` | `data-model.objectschema.ontology-entity`        | `technology.systemsoftware.sqlalchemy`               | `technology` | `depends-on` | many-to-many | medium   |
| `data-model.objectschema.depends-on.technology.systemsoftware` | `data-model.objectschema.pipeline-configuration` | `technology.systemsoftware.sqlalchemy`               | `technology` | `depends-on` | many-to-many | medium   |
| `data-model.objectschema.maps-to.api.requestbody`              | `data-model.objectschema.property-definition`    | `api.requestbody.property-definition-create-request` | `api`        | `maps-to`    | many-to-many | medium   |
| `data-model.objectschema.maps-to.api.response`                 | `data-model.objectschema.property-definition`    | `api.response.property-definition-response`          | `api`        | `maps-to`    | many-to-many | medium   |
| `data-model.objectschema.depends-on.technology.systemsoftware` | `data-model.objectschema.relationship`           | `technology.systemsoftware.sqlalchemy`               | `technology` | `depends-on` | many-to-many | medium   |

## Element Reference

### external_references list {#external-references-list}

**ID**: `data-model.arrayschema.external-references-list`

**Type**: `arrayschema`

Array schema for the external_references list on the Class entity — holds enrichment references from ConceptNet, DBpedia, Wikidata, and schema.org

#### Attributes

| Name        | Value  |
| ----------- | ------ |
| items       | string |
| minItems    | 0      |
| uniqueItems | true   |

#### Relationships

| Type        | Related Element                                | Predicate    | Direction |
| ----------- | ---------------------------------------------- | ------------ | --------- |
| intra-layer | `data-model.numericschema.relationship-weight` | `aggregates` | outbound  |
| intra-layer | `data-model.objectschema.ontology-entity`      | `aggregates` | outbound  |
| intra-layer | `data-model.stringschema.iso-8601-datetime`    | `aggregates` | outbound  |
| intra-layer | `data-model.stringschema.uuid-string`          | `aggregates` | outbound  |

### relationship weight {#relationship-weight}

**ID**: `data-model.numericschema.relationship-weight`

**Type**: `numericschema`

Float schema for the weight property on typed relationships — defaults to 1.0, used for semantic similarity scoring and graph traversal

#### Attributes

| Name    | Value  |
| ------- | ------ |
| maximum | 1      |
| minimum | 0      |
| type    | number |

#### Relationships

| Type        | Related Element                                   | Predicate    | Direction |
| ----------- | ------------------------------------------------- | ------------ | --------- |
| intra-layer | `data-model.arrayschema.external-references-list` | `aggregates` | inbound   |

### Change Event {#change-event}

**ID**: `data-model.objectschema.change-event`

**Type**: `objectschema`

ORM schema for the audit trail of all entity mutations — stores entity_id, entity_type, operation (CREATE/UPDATE/DELETE), new_state and previous_state JSON snapshots, user_id, change_reason, and optional import_run_id correlation

#### Relationships

| Type        | Related Element                           | Predicate    | Direction |
| ----------- | ----------------------------------------- | ------------ | --------- |
| inter-layer | `technology.systemsoftware.sqlalchemy`    | `depends-on` | outbound  |
| intra-layer | `data-model.objectschema.ontology-entity` | `extends`    | outbound  |
| intra-layer | `data-model.objectschema.import-run`      | `extends`    | inbound   |

### Changeset {#changeset}

**ID**: `data-model.objectschema.changeset`

**Type**: `objectschema`

ORM schema for named collections of change events progressing through version control states (WORKING→STAGED→PROPOSED→APPROVED→MERGED) — stores name, description, state, and a JSON array of event_ids

#### Relationships

| Type        | Related Element                           | Predicate    | Direction |
| ----------- | ----------------------------------------- | ------------ | --------- |
| inter-layer | `technology.systemsoftware.sqlalchemy`    | `depends-on` | outbound  |
| intra-layer | `data-model.objectschema.changeset-event` | `extends`    | outbound  |
| intra-layer | `data-model.objectschema.proposal`        | `extends`    | outbound  |
| intra-layer | `data-model.objectschema.import-run`      | `extends`    | inbound   |

### Changeset Event {#changeset-event}

**ID**: `data-model.objectschema.changeset-event`

**Type**: `objectschema`

ORM schema for individual change events within a versioning changeset — stores changeset_id FK, entity_id, operation (create/update/delete), before/after JSON snapshots

#### Relationships

| Type        | Related Element                     | Predicate | Direction |
| ----------- | ----------------------------------- | --------- | --------- |
| intra-layer | `data-model.objectschema.changeset` | `extends` | inbound   |

### Conflict Resolution {#conflict-resolution}

**ID**: `data-model.objectschema.conflict-resolution`

**Type**: `objectschema`

ORM schema for manual conflict resolution records — stores proposal_id FK, entity_id, conflict type, chosen resolution strategy, and resolved snapshot

#### Relationships

| Type        | Related Element                    | Predicate | Direction |
| ----------- | ---------------------------------- | --------- | --------- |
| intra-layer | `data-model.objectschema.proposal` | `extends` | inbound   |

### Entity Version {#entity-version}

**ID**: `data-model.objectschema.entity-version`

**Type**: `objectschema`

ORM schema for entity version snapshots — stores entity_id FK, version number, full JSON snapshot, and the change event that triggered the version

#### Relationships

| Type        | Related Element                        | Predicate | Direction |
| ----------- | -------------------------------------- | --------- | --------- |
| inter-layer | `api.response.entity-version-response` | `maps-to` | outbound  |

### Extraction Result {#extraction-result}

**ID**: `data-model.objectschema.extraction-result`

**Type**: `objectschema`

ORM schema for persisted extraction results — stores source text, NLP/LLM pipeline output (JSON), extracted entity IDs, processing metrics, and run timestamps

#### Relationships

| Type        | Related Element                         | Predicate | Direction |
| ----------- | --------------------------------------- | --------- | --------- |
| inter-layer | `api.response.extraction-result-schema` | `maps-to` | outbound  |

### Import Run {#import-run}

**ID**: `data-model.objectschema.import-run`

**Type**: `objectschema`

ORM schema tracking interchange import operations (SKOS/OWL/GraphML) — stores format, source_hash, source_uri, scope, status (PENDING/COMMITTED/FAILED/ROLLED_BACK), resolution records, and created_by for auditability

#### Relationships

| Type        | Related Element                        | Predicate    | Direction |
| ----------- | -------------------------------------- | ------------ | --------- |
| inter-layer | `technology.systemsoftware.sqlalchemy` | `depends-on` | outbound  |
| intra-layer | `data-model.objectschema.change-event` | `extends`    | outbound  |
| intra-layer | `data-model.objectschema.changeset`    | `extends`    | outbound  |

### Individual Class {#individual-class}

**ID**: `data-model.objectschema.individual-class`

**Type**: `objectschema`

Association table ORM schema linking individual instances to their parent classes — stores individual_id, class_id FK pair with ordering index for class priority

#### Relationships

| Type        | Related Element                                 | Predicate | Direction |
| ----------- | ----------------------------------------------- | --------- | --------- |
| inter-layer | `api.requestbody.individual-class-list-request` | `maps-to` | outbound  |
| inter-layer | `api.requestbody.individual-class-request`      | `maps-to` | outbound  |

### Ontology Entity {#ontology-entity}

**ID**: `data-model.objectschema.ontology-entity`

**Type**: `objectschema`

Single-table inheritance ORM schema for all ontology entities (taxonomy, concept_scheme, class, individual, property_definition) — stores title, description, hierarchy FKs, JSON value objects (external_references, lexical_senses, data_properties), binary embedding, and optimistic-locking version

#### Relationships

| Type        | Related Element                                   | Predicate    | Direction |
| ----------- | ------------------------------------------------- | ------------ | --------- |
| inter-layer | `technology.systemsoftware.sqlalchemy`            | `depends-on` | outbound  |
| intra-layer | `data-model.arrayschema.external-references-list` | `aggregates` | inbound   |
| intra-layer | `data-model.objectschema.change-event`            | `extends`    | inbound   |
| intra-layer | `data-model.objectschema.relationship`            | `extends`    | outbound  |

### Pipeline Configuration {#pipeline-configuration}

**ID**: `data-model.objectschema.pipeline-configuration`

**Type**: `objectschema`

ORM schema for LLM pipeline configurations in operations.db — stores pipeline slug, title, provider, model, config JSON, system_prompt, user_prompt template, enabled flag, and version counter

#### Relationships

| Type        | Related Element                              | Predicate    | Direction |
| ----------- | -------------------------------------------- | ------------ | --------- |
| inter-layer | `technology.systemsoftware.sqlalchemy`       | `depends-on` | outbound  |
| intra-layer | `data-model.objectschema.pipeline-execution` | `extends`    | outbound  |

### Pipeline Execution {#pipeline-execution}

**ID**: `data-model.objectschema.pipeline-execution`

**Type**: `objectschema`

ORM schema for pipeline execution records in operations.db — stores pipeline_id FK, trigger, status, input/output JSON, LLM traceability log, and timing metadata

#### Relationships

| Type        | Related Element                                  | Predicate | Direction |
| ----------- | ------------------------------------------------ | --------- | --------- |
| intra-layer | `data-model.objectschema.pipeline-configuration` | `extends` | inbound   |

### Property Definition {#property-definition}

**ID**: `data-model.objectschema.property-definition`

**Type**: `objectschema`

ORM schema for property definitions (relationship types/object properties) — stores name, description, domain_id and range_id class FKs, and optional inverse property ID

#### Relationships

| Type        | Related Element                                      | Predicate | Direction |
| ----------- | ---------------------------------------------------- | --------- | --------- |
| inter-layer | `api.requestbody.property-definition-create-request` | `maps-to` | outbound  |
| inter-layer | `api.response.property-definition-response`          | `maps-to` | outbound  |

### Proposal {#proposal}

**ID**: `data-model.objectschema.proposal`

**Type**: `objectschema`

ORM schema for merge proposals — stores changeset_id FK, submitter, status (pending/approved/rejected/merged), review metadata, and conflict resolution references

#### Relationships

| Type        | Related Element                               | Predicate | Direction |
| ----------- | --------------------------------------------- | --------- | --------- |
| intra-layer | `data-model.objectschema.changeset`           | `extends` | inbound   |
| intra-layer | `data-model.objectschema.conflict-resolution` | `extends` | outbound  |

### Relationship {#relationship}

**ID**: `data-model.objectschema.relationship`

**Type**: `objectschema`

ORM schema for typed directed edges between ontology entities — stores source_id, target_id, optional property_definition_id FK, float weight (0–1), and JSON metadata; used by GraphAnalysisService for graph construction

#### Relationships

| Type        | Related Element                           | Predicate    | Direction |
| ----------- | ----------------------------------------- | ------------ | --------- |
| inter-layer | `technology.systemsoftware.sqlalchemy`    | `depends-on` | outbound  |
| intra-layer | `data-model.objectschema.ontology-entity` | `extends`    | inbound   |

### ISO 8601 datetime {#iso-8601-datetime}

**ID**: `data-model.stringschema.iso-8601-datetime`

**Type**: `stringschema`

String schema for timestamp fields (created_at, updated_at) — ISO 8601 format stored as TEXT in SQLite

#### Attributes

| Name   | Value     |
| ------ | --------- |
| format | date-time |
| type   | string    |

#### Relationships

| Type        | Related Element                                   | Predicate    | Direction |
| ----------- | ------------------------------------------------- | ------------ | --------- |
| intra-layer | `data-model.arrayschema.external-references-list` | `aggregates` | inbound   |

### UUID string {#uuid-string}

**ID**: `data-model.stringschema.uuid-string`

**Type**: `stringschema`

String schema for entity identifiers — UUID v4 format, used as primary keys across all ontology entities and stored as TEXT in SQLite

#### Attributes

| Name      | Value  |
| --------- | ------ |
| format    | uuid   |
| maxLength | 36     |
| minLength | 36     |
| type      | string |

#### Relationships

| Type        | Related Element                                   | Predicate    | Direction |
| ----------- | ------------------------------------------------- | ------------ | --------- |
| intra-layer | `data-model.arrayschema.external-references-list` | `aggregates` | inbound   |

---

Generated: 2026-05-08T11:56:41.266Z | Model Version: 0.1.0

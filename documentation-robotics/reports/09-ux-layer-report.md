# UX

User interface components, screens, and user experience elements.

## Report Index

- [Layer Introduction](#layer-introduction)
- [Intra-Layer Relationships](#intra-layer-relationships)
- [Inter-Layer Dependencies](#inter-layer-dependencies)
- [Inter-Layer Relationships Table](#inter-layer-relationships-table)
- [Element Reference](#element-reference)

## Layer Introduction

| Metric                    | Count |
| ------------------------- | ----- |
| Elements                  | 14    |
| Intra-Layer Relationships | 3     |
| Inter-Layer Relationships | 42    |
| Inbound Relationships     | 22    |
| Outbound Relationships    | 20    |

**Cross-Layer References**:

- **Upstream layers**: [APM](./11-apm-layer-report.md), [Navigation](./10-navigation-layer-report.md), [Testing](./12-testing-layer-report.md)
- **Downstream layers**: [API](./06-api-layer-report.md), [Motivation](./01-motivation-layer-report.md), [Security](./03-security-layer-report.md)

## Intra-Layer Relationships

```mermaid
flowchart LR
  subgraph ux
    ux_experiencestate_entity_crud_state["Entity CRUD State"]
    ux_librarycomponent_flowbite_react_components["Flowbite React Components"]
    ux_statepattern_crud_entity_pattern["CRUD Entity Pattern"]
    ux_uxapplication_context_studio_spa["Context Studio SPA"]
    ux_uxlibrary_flowbite_react_component_library["Flowbite React Component Library"]
    ux_uxspec_ontology_editor_ux_spec["Ontology Editor UX Spec"]
    ux_view_admin_view["Admin View"]
    ux_view_configuration_view["Configuration View"]
    ux_view_datasets_view["Datasets View"]
    ux_view_domains_view["Domains View"]
    ux_view_layers_view["Layers View"]
    ux_view_predicates_view["Predicates View"]
    ux_view_rag_experiments_view["RAG Experiments View"]
    ux_view_terms_view["Terms View"]
    ux_statepattern_crud_entity_pattern -->|governs| ux_experiencestate_entity_crud_state
    ux_uxapplication_context_studio_spa -->|aggregates| ux_uxspec_ontology_editor_ux_spec
    ux_uxlibrary_flowbite_react_component_library -->|aggregates| ux_librarycomponent_flowbite_react_components
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
  apm --> ux
  navigation --> ux
  testing --> ux
  ux --> api
  ux --> motivation
  ux --> security
  class ux current
```

## Inter-Layer Relationships Table

| Relationship ID                             | Source Node                                         | Dest Node                                          | Dest Layer   | Predicate  | Cardinality  | Strength |
| ------------------------------------------- | --------------------------------------------------- | -------------------------------------------------- | ------------ | ---------- | ------------ | -------- |
| `apm.metricinstrument.monitors.ux.view`     | `apm.metricinstrument.rag-processing-time`          | `ux.view.rag-experiments-view`                     | `ux`         | `monitors` | many-to-many | medium   |
| `apm.span.monitors.ux.view`                 | `apm.span.api-request-span`                         | `ux.view.layers-view`                              | `ux`         | `monitors` | many-to-many | medium   |
| `apm.span.monitors.ux.view`                 | `apm.span.api-request-span`                         | `ux.view.rag-experiments-view`                     | `ux`         | `monitors` | many-to-many | medium   |
| `apm.span.monitors.ux.view`                 | `apm.span.database-query-span`                      | `ux.view.datasets-view`                            | `ux`         | `monitors` | many-to-many | medium   |
| `apm.span.monitors.ux.view`                 | `apm.span.database-query-span`                      | `ux.view.layers-view`                              | `ux`         | `monitors` | many-to-many | medium   |
| `apm.span.monitors.ux.view`                 | `apm.span.database-query-span`                      | `ux.view.terms-view`                               | `ux`         | `monitors` | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`          | `navigation.route.admin-route`                      | `ux.view.admin-view`                               | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`          | `navigation.route.configuration-route`              | `ux.view.configuration-view`                       | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`          | `navigation.route.datasets-route`                   | `ux.view.datasets-view`                            | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`          | `navigation.route.domains-route`                    | `ux.view.domains-view`                             | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`          | `navigation.route.layers-route`                     | `ux.view.layers-view`                              | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`          | `navigation.route.predicates-route`                 | `ux.view.predicates-view`                          | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`          | `navigation.route.rag-experiments-route`            | `ux.view.rag-experiments-view`                     | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`          | `navigation.route.terms-route`                      | `ux.view.terms-view`                               | `ux`         | `maps-to`  | many-to-many | medium   |
| `testing.testcoveragetarget.covers.ux.view` | `testing.testcoveragetarget.admin-health`           | `ux.view.admin-view`                               | `ux`         | `covers`   | many-to-many | medium   |
| `testing.testcoveragetarget.covers.ux.view` | `testing.testcoveragetarget.extraction-pipeline`    | `ux.view.rag-experiments-view`                     | `ux`         | `covers`   | many-to-many | medium   |
| `testing.testcoveragetarget.covers.ux.view` | `testing.testcoveragetarget.graph-analysis`         | `ux.view.rag-experiments-view`                     | `ux`         | `covers`   | many-to-many | medium   |
| `testing.testcoveragetarget.covers.ux.view` | `testing.testcoveragetarget.llm-pipeline-execution` | `ux.view.rag-experiments-view`                     | `ux`         | `covers`   | many-to-many | medium   |
| `testing.testcoveragetarget.covers.ux.view` | `testing.testcoveragetarget.ontology-crud`          | `ux.view.domains-view`                             | `ux`         | `covers`   | many-to-many | medium   |
| `testing.testcoveragetarget.covers.ux.view` | `testing.testcoveragetarget.ontology-crud`          | `ux.view.layers-view`                              | `ux`         | `covers`   | many-to-many | medium   |
| `testing.testcoveragetarget.covers.ux.view` | `testing.testcoveragetarget.ontology-crud`          | `ux.view.terms-view`                               | `ux`         | `covers`   | many-to-many | medium   |
| `testing.testcoveragetarget.covers.ux.view` | `testing.testcoveragetarget.versioning-workflow`    | `ux.view.datasets-view`                            | `ux`         | `covers`   | many-to-many | medium   |
| `ux.view.requires.security.role`            | `ux.view.admin-view`                                | `security.role.administrator`                      | `security`   | `requires` | many-to-many | medium   |
| `ux.view.serves.motivation.stakeholder`     | `ux.view.admin-view`                                | `motivation.stakeholder.platform-developer`        | `motivation` | `serves`   | many-to-many | medium   |
| `ux.view.uses.api.securityscheme`           | `ux.view.admin-view`                                | `api.securityscheme.api-key`                       | `api`        | `uses`     | many-to-many | medium   |
| `ux.view.serves.motivation.stakeholder`     | `ux.view.configuration-view`                        | `motivation.stakeholder.platform-developer`        | `motivation` | `serves`   | many-to-many | medium   |
| `ux.view.uses.api.securityscheme`           | `ux.view.configuration-view`                        | `api.securityscheme.api-key`                       | `api`        | `uses`     | many-to-many | medium   |
| `ux.view.serves.motivation.stakeholder`     | `ux.view.datasets-view`                             | `motivation.stakeholder.knowledge-manager`         | `motivation` | `serves`   | many-to-many | medium   |
| `ux.view.uses.api.securityscheme`           | `ux.view.datasets-view`                             | `api.securityscheme.api-key`                       | `api`        | `uses`     | many-to-many | medium   |
| `ux.view.serves.motivation.stakeholder`     | `ux.view.domains-view`                              | `motivation.stakeholder.knowledge-manager`         | `motivation` | `serves`   | many-to-many | medium   |
| `ux.view.uses.api.securityscheme`           | `ux.view.domains-view`                              | `api.securityscheme.api-key`                       | `api`        | `uses`     | many-to-many | medium   |
| `ux.view.maps-to.motivation.outcome`        | `ux.view.layers-view`                               | `motivation.outcome.curated-domain-ontology`       | `motivation` | `maps-to`  | many-to-many | medium   |
| `ux.view.requires.security.role`            | `ux.view.layers-view`                               | `security.role.administrator`                      | `security`   | `requires` | many-to-many | medium   |
| `ux.view.serves.motivation.stakeholder`     | `ux.view.layers-view`                               | `motivation.stakeholder.knowledge-manager`         | `motivation` | `serves`   | many-to-many | medium   |
| `ux.view.uses.api.securityscheme`           | `ux.view.layers-view`                               | `api.securityscheme.api-key`                       | `api`        | `uses`     | many-to-many | medium   |
| `ux.view.serves.motivation.stakeholder`     | `ux.view.predicates-view`                           | `motivation.stakeholder.knowledge-manager`         | `motivation` | `serves`   | many-to-many | medium   |
| `ux.view.uses.api.securityscheme`           | `ux.view.predicates-view`                           | `api.securityscheme.api-key`                       | `api`        | `uses`     | many-to-many | medium   |
| `ux.view.maps-to.motivation.outcome`        | `ux.view.rag-experiments-view`                      | `motivation.outcome.improved-ai-inference-quality` | `motivation` | `maps-to`  | many-to-many | medium   |
| `ux.view.serves.motivation.stakeholder`     | `ux.view.rag-experiments-view`                      | `motivation.stakeholder.ai-agent-consumer`         | `motivation` | `serves`   | many-to-many | medium   |
| `ux.view.uses.api.securityscheme`           | `ux.view.rag-experiments-view`                      | `api.securityscheme.api-key`                       | `api`        | `uses`     | many-to-many | medium   |
| `ux.view.serves.motivation.stakeholder`     | `ux.view.terms-view`                                | `motivation.stakeholder.knowledge-manager`         | `motivation` | `serves`   | many-to-many | medium   |
| `ux.view.uses.api.securityscheme`           | `ux.view.terms-view`                                | `api.securityscheme.api-key`                       | `api`        | `uses`     | many-to-many | medium   |

## Element Reference

### Entity CRUD State {#entity-crud-state}

**ID**: `ux.experiencestate.entity-crud-state`

**Type**: `experiencestate`

The composite experience state representing the loading, success, and error states for entity CRUD operations in the Context Studio SPA. Governs component visibility and enabled/disabled states during entity create, read, update, and delete workflows.

#### Attributes

| Name    | Value |
| ------- | ----- |
| channel | web   |
| initial | false |

#### Relationships

| Type        | Related Element                       | Predicate | Direction |
| ----------- | ------------------------------------- | --------- | --------- |
| intra-layer | `ux.statepattern.crud-entity-pattern` | `governs` | inbound   |

### Flowbite React Components {#flowbite-react-components}

**ID**: `ux.librarycomponent.flowbite-react-components`

**Type**: `librarycomponent`

The Flowbite React component set used throughout the Context Studio SPA. Provides buttons, modals, tables, forms, badges, and other UI primitives built on Tailwind CSS, composing the visual layer of all views.

#### Attributes

| Name     | Value         |
| -------- | ------------- |
| category | ui-primitives |
| type     | display       |

#### Relationships

| Type        | Related Element                                 | Predicate    | Direction |
| ----------- | ----------------------------------------------- | ------------ | --------- |
| intra-layer | `ux.uxlibrary.flowbite-react-component-library` | `aggregates` | inbound   |

### CRUD Entity Pattern {#crud-entity-pattern}

**ID**: `ux.statepattern.crud-entity-pattern`

**Type**: `statepattern`

State pattern for create/read/update/delete operations on ontology entities: idle -&gt; form open -&gt; submitting -&gt; success/error

#### Attributes

| Name        | Value                                                      |
| ----------- | ---------------------------------------------------------- |
| category    | form                                                       |
| description | Standard CRUD state machine for ontology entity operations |

#### Relationships

| Type        | Related Element                        | Predicate | Direction |
| ----------- | -------------------------------------- | --------- | --------- |
| intra-layer | `ux.experiencestate.entity-crud-state` | `governs` | outbound  |

### Context Studio SPA {#context-studio-spa}

**ID**: `ux.uxapplication.context-studio-spa`

**Type**: `uxapplication`

React single-page application for knowledge graph management — the shared front end connecting to the local-server API

#### Attributes

| Name        | Value                                           |
| ----------- | ----------------------------------------------- |
| channel     | web                                             |
| description | Local-first knowledge graph editor and RAG tool |
| version     | 1.0.0                                           |

#### Relationships

| Type        | Related Element                     | Predicate    | Direction |
| ----------- | ----------------------------------- | ------------ | --------- |
| intra-layer | `ux.uxspec.ontology-editor-ux-spec` | `aggregates` | outbound  |

### Flowbite React Component Library {#flowbite-react-component-library}

**ID**: `ux.uxlibrary.flowbite-react-component-library`

**Type**: `uxlibrary`

Primary UI component library (Flowbite React + Tailwind CSS) providing form controls, tables, modals, and layout primitives

#### Attributes

| Name        | Value                                              |
| ----------- | -------------------------------------------------- |
| description | Flowbite React component library with Tailwind CSS |
| version     | latest                                             |

#### Relationships

| Type        | Related Element                                 | Predicate    | Direction |
| ----------- | ----------------------------------------------- | ------------ | --------- |
| intra-layer | `ux.librarycomponent.flowbite-react-components` | `aggregates` | outbound  |

### Ontology Editor UX Spec {#ontology-editor-ux-spec}

**ID**: `ux.uxspec.ontology-editor-ux-spec`

**Type**: `uxspec`

UX specification for the Ontology Editor experience within Context Studio SPA. Covers the views for managing layers, domains, terms, predicates, datasets, and configuration within the React/Vite front-end.

#### Attributes

| Name       | Value  |
| ---------- | ------ |
| experience | visual |
| version    | 0.1.0  |

#### Relationships

| Type        | Related Element                       | Predicate    | Direction |
| ----------- | ------------------------------------- | ------------ | --------- |
| intra-layer | `ux.uxapplication.context-studio-spa` | `aggregates` | inbound   |

### Admin View {#admin-view}

**ID**: `ux.view.admin-view`

**Type**: `view`

Administrative view for system health monitoring, background task management, and schema migration

#### Attributes

| Name     | Value |
| -------- | ----- |
| routable | true  |
| title    | Admin |
| type     | page  |

#### Relationships

| Type        | Related Element                             | Predicate  | Direction |
| ----------- | ------------------------------------------- | ---------- | --------- |
| inter-layer | `navigation.route.admin-route`              | `maps-to`  | inbound   |
| inter-layer | `testing.testcoveragetarget.admin-health`   | `covers`   | inbound   |
| inter-layer | `security.role.administrator`               | `requires` | outbound  |
| inter-layer | `motivation.stakeholder.platform-developer` | `serves`   | outbound  |
| inter-layer | `api.securityscheme.api-key`                | `uses`     | outbound  |

### Configuration View {#configuration-view}

**ID**: `ux.view.configuration-view`

**Type**: `view`

Page view for server configuration management and LLM pipeline settings

#### Attributes

| Name     | Value         |
| -------- | ------------- |
| routable | true          |
| title    | Configuration |
| type     | page          |

#### Relationships

| Type        | Related Element                             | Predicate | Direction |
| ----------- | ------------------------------------------- | --------- | --------- |
| inter-layer | `navigation.route.configuration-route`      | `maps-to` | inbound   |
| inter-layer | `motivation.stakeholder.platform-developer` | `serves`  | outbound  |
| inter-layer | `api.securityscheme.api-key`                | `uses`    | outbound  |

### Datasets View {#datasets-view}

**ID**: `ux.view.datasets-view`

**Type**: `view`

Page view for dataset workspace management — list, create, activate, and switch between SQLite dataset files

#### Attributes

| Name     | Value    |
| -------- | -------- |
| routable | true     |
| title    | Datasets |
| type     | page     |

#### Relationships

| Type        | Related Element                                  | Predicate  | Direction |
| ----------- | ------------------------------------------------ | ---------- | --------- |
| inter-layer | `apm.span.database-query-span`                   | `monitors` | inbound   |
| inter-layer | `navigation.route.datasets-route`                | `maps-to`  | inbound   |
| inter-layer | `testing.testcoveragetarget.versioning-workflow` | `covers`   | inbound   |
| inter-layer | `motivation.stakeholder.knowledge-manager`       | `serves`   | outbound  |
| inter-layer | `api.securityscheme.api-key`                     | `uses`     | outbound  |

### Domains View {#domains-view}

**ID**: `ux.view.domains-view`

**Type**: `view`

Page view for managing concept scheme entities within a taxonomy

#### Attributes

| Name     | Value   |
| -------- | ------- |
| routable | true    |
| title    | Domains |
| type     | page    |

#### Relationships

| Type        | Related Element                            | Predicate | Direction |
| ----------- | ------------------------------------------ | --------- | --------- |
| inter-layer | `navigation.route.domains-route`           | `maps-to` | inbound   |
| inter-layer | `testing.testcoveragetarget.ontology-crud` | `covers`  | inbound   |
| inter-layer | `motivation.stakeholder.knowledge-manager` | `serves`  | outbound  |
| inter-layer | `api.securityscheme.api-key`               | `uses`    | outbound  |

### Layers View {#layers-view}

**ID**: `ux.view.layers-view`

**Type**: `view`

Page view for managing taxonomy entities — list, create, edit, and delete taxonomies (Layers)

#### Attributes

| Name     | Value  |
| -------- | ------ |
| routable | true   |
| title    | Layers |
| type     | page   |

#### Relationships

| Type        | Related Element                              | Predicate  | Direction |
| ----------- | -------------------------------------------- | ---------- | --------- |
| inter-layer | `apm.span.api-request-span`                  | `monitors` | inbound   |
| inter-layer | `apm.span.database-query-span`               | `monitors` | inbound   |
| inter-layer | `navigation.route.layers-route`              | `maps-to`  | inbound   |
| inter-layer | `testing.testcoveragetarget.ontology-crud`   | `covers`   | inbound   |
| inter-layer | `motivation.outcome.curated-domain-ontology` | `maps-to`  | outbound  |
| inter-layer | `security.role.administrator`                | `requires` | outbound  |
| inter-layer | `motivation.stakeholder.knowledge-manager`   | `serves`   | outbound  |
| inter-layer | `api.securityscheme.api-key`                 | `uses`     | outbound  |

### Predicates View {#predicates-view}

**ID**: `ux.view.predicates-view`

**Type**: `view`

Page view for managing property definitions in the ontology

#### Attributes

| Name     | Value      |
| -------- | ---------- |
| routable | true       |
| title    | Predicates |
| type     | page       |

#### Relationships

| Type        | Related Element                            | Predicate | Direction |
| ----------- | ------------------------------------------ | --------- | --------- |
| inter-layer | `navigation.route.predicates-route`        | `maps-to` | inbound   |
| inter-layer | `motivation.stakeholder.knowledge-manager` | `serves`  | outbound  |
| inter-layer | `api.securityscheme.api-key`               | `uses`    | outbound  |

### RAG Experiments View {#rag-experiments-view}

**ID**: `ux.view.rag-experiments-view`

**Type**: `view`

View for managing RAG test paragraphs, running experiments, and comparing pipeline results

#### Attributes

| Name     | Value           |
| -------- | --------------- |
| routable | true            |
| title    | RAG Experiments |
| type     | page            |

#### Relationships

| Type        | Related Element                                     | Predicate  | Direction |
| ----------- | --------------------------------------------------- | ---------- | --------- |
| inter-layer | `apm.metricinstrument.rag-processing-time`          | `monitors` | inbound   |
| inter-layer | `apm.span.api-request-span`                         | `monitors` | inbound   |
| inter-layer | `navigation.route.rag-experiments-route`            | `maps-to`  | inbound   |
| inter-layer | `testing.testcoveragetarget.extraction-pipeline`    | `covers`   | inbound   |
| inter-layer | `testing.testcoveragetarget.graph-analysis`         | `covers`   | inbound   |
| inter-layer | `testing.testcoveragetarget.llm-pipeline-execution` | `covers`   | inbound   |
| inter-layer | `motivation.outcome.improved-ai-inference-quality`  | `maps-to`  | outbound  |
| inter-layer | `motivation.stakeholder.ai-agent-consumer`          | `serves`   | outbound  |
| inter-layer | `api.securityscheme.api-key`                        | `uses`     | outbound  |

### Terms View {#terms-view}

**ID**: `ux.view.terms-view`

**Type**: `view`

Page view for managing class entities within a concept scheme, including relationship editing

#### Attributes

| Name     | Value |
| -------- | ----- |
| routable | true  |
| title    | Terms |
| type     | page  |

#### Relationships

| Type        | Related Element                            | Predicate  | Direction |
| ----------- | ------------------------------------------ | ---------- | --------- |
| inter-layer | `apm.span.database-query-span`             | `monitors` | inbound   |
| inter-layer | `navigation.route.terms-route`             | `maps-to`  | inbound   |
| inter-layer | `testing.testcoveragetarget.ontology-crud` | `covers`   | inbound   |
| inter-layer | `motivation.stakeholder.knowledge-manager` | `serves`   | outbound  |
| inter-layer | `api.securityscheme.api-key`               | `uses`     | outbound  |

---

Generated: 2026-05-07T22:00:51.579Z | Model Version: 0.1.0

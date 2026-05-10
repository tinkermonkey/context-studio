# Navigation

Application routing, navigation flows, and page structures.

## Report Index

- [Layer Introduction](#layer-introduction)
- [Intra-Layer Relationships](#intra-layer-relationships)
- [Inter-Layer Dependencies](#inter-layer-dependencies)
- [Inter-Layer Relationships Table](#inter-layer-relationships-table)
- [Element Reference](#element-reference)

## Layer Introduction

| Metric                    | Count |
| ------------------------- | ----- |
| Elements                  | 13    |
| Intra-Layer Relationships | 4     |
| Inter-Layer Relationships | 15    |
| Inbound Relationships     | 4     |
| Outbound Relationships    | 11    |

**Cross-Layer References**:

- **Upstream layers**: [APM](./11-apm-layer-report.md)
- **Downstream layers**: [UX](./09-ux-layer-report.md)

## Intra-Layer Relationships

```mermaid
flowchart LR
  subgraph navigation
    navigation_navigationflow_ontology_hierarchy_flow["Ontology Hierarchy Flow"]
    navigation_route_admin_route["Admin Route"]
    navigation_route_app_root_route["App Root Route"]
    navigation_route_classes_route["Classes Route"]
    navigation_route_concept_schemes_route["Concept Schemes Route"]
    navigation_route_configuration_route["Configuration Route"]
    navigation_route_datasets_route["Datasets Route"]
    navigation_route_individuals_route["Individuals Route"]
    navigation_route_interchange_route["Interchange Route"]
    navigation_route_properties_route["Properties Route"]
    navigation_route_rag_experiments_route["RAG Experiments Route"]
    navigation_route_relationships_route["Relationships Route"]
    navigation_route_taxonomies_route["Taxonomies Route"]
    navigation_route_app_root_route -->|navigates-to| navigation_route_admin_route
    navigation_route_app_root_route -->|navigates-to| navigation_route_configuration_route
    navigation_route_app_root_route -->|navigates-to| navigation_route_datasets_route
    navigation_route_app_root_route -->|navigates-to| navigation_route_rag_experiments_route
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
  apm --> navigation
  navigation --> ux
  class navigation current
```

## Inter-Layer Relationships Table

| Relationship ID                                  | Source Node                                        | Dest Node                                           | Dest Layer   | Predicate  | Cardinality  | Strength |
| ------------------------------------------------ | -------------------------------------------------- | --------------------------------------------------- | ------------ | ---------- | ------------ | -------- |
| `apm.metricinstrument.monitors.navigation.route` | `apm.metricinstrument.background-task-queue-depth` | `navigation.route.admin-route`                      | `navigation` | `monitors` | many-to-many | medium   |
| `apm.metricinstrument.monitors.navigation.route` | `apm.metricinstrument.llm-execution-tracker`       | `navigation.route.rag-experiments-route`            | `navigation` | `monitors` | many-to-many | medium   |
| `apm.metricinstrument.monitors.navigation.route` | `apm.metricinstrument.rag-processing-time`         | `navigation.route.rag-experiments-route`            | `navigation` | `monitors` | many-to-many | medium   |
| `apm.span.monitors.navigation.navigationflow`    | `apm.span.api-request-span`                        | `navigation.navigationflow.ontology-hierarchy-flow` | `navigation` | `monitors` | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.admin-route`                     | `ux.view.admin-view`                                | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.classes-route`                   | `ux.view.classes-view`                              | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.concept-schemes-route`           | `ux.view.concept-schemes-view`                      | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.configuration-route`             | `ux.view.configuration-view`                        | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.datasets-route`                  | `ux.view.datasets-view`                             | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.individuals-route`               | `ux.view.individuals-view`                          | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.interchange-route`               | `ux.view.interchange-view`                          | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.properties-route`                | `ux.view.properties-view`                           | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.rag-experiments-route`           | `ux.view.rag-experiments-view`                      | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.relationships-route`             | `ux.view.relationships-view`                        | `ux`         | `maps-to`  | many-to-many | medium   |
| `navigation.route.maps-to.ux.view`               | `navigation.route.taxonomies-route`                | `ux.view.taxonomies-view`                           | `ux`         | `maps-to`  | many-to-many | medium   |

## Element Reference

### Ontology Hierarchy Flow {#ontology-hierarchy-flow}

**ID**: `navigation.navigationflow.ontology-hierarchy-flow`

**Type**: `navigationflow`

Three-step navigation flow guiding the user through the knowledge graph hierarchy: Taxonomies -&gt; Concept Schemes -&gt; Classes

#### Attributes

| Name        | Value                                                                      |
| ----------- | -------------------------------------------------------------------------- |
| description | Hierarchical drill-down through taxonomy, concept scheme, and class levels |

#### Relationships

| Type        | Related Element             | Predicate  | Direction |
| ----------- | --------------------------- | ---------- | --------- |
| inter-layer | `apm.span.api-request-span` | `monitors` | inbound   |

### Admin Route {#admin-route}

**ID**: `navigation.route.admin-route`

**Type**: `route`

Route serving the administrative monitoring and health view

#### Attributes

| Name  | Value  |
| ----- | ------ |
| title | Admin  |
| type  | public |

#### Relationships

| Type        | Related Element                                    | Predicate      | Direction |
| ----------- | -------------------------------------------------- | -------------- | --------- |
| inter-layer | `apm.metricinstrument.background-task-queue-depth` | `monitors`     | inbound   |
| inter-layer | `ux.view.admin-view`                               | `maps-to`      | outbound  |
| intra-layer | `navigation.route.app-root-route`                  | `navigates-to` | inbound   |

### App Root Route {#app-root-route}

**ID**: `navigation.route.app-root-route`

**Type**: `route`

Root application layout route — renders the navigation shell, sidebar, and main content area

#### Attributes

| Name  | Value          |
| ----- | -------------- |
| title | Context Studio |
| type  | public         |

#### Relationships

| Type        | Related Element                          | Predicate      | Direction |
| ----------- | ---------------------------------------- | -------------- | --------- |
| intra-layer | `navigation.route.admin-route`           | `navigates-to` | outbound  |
| intra-layer | `navigation.route.configuration-route`   | `navigates-to` | outbound  |
| intra-layer | `navigation.route.datasets-route`        | `navigates-to` | outbound  |
| intra-layer | `navigation.route.rag-experiments-route` | `navigates-to` | outbound  |

### Classes Route {#classes-route}

**ID**: `navigation.route.classes-route`

**Type**: `route`

Route for /app/classes — renders Classes View

#### Attributes

| Name | Value     |
| ---- | --------- |
| type | protected |

#### Relationships

| Type        | Related Element        | Predicate | Direction |
| ----------- | ---------------------- | --------- | --------- |
| inter-layer | `ux.view.classes-view` | `maps-to` | outbound  |

### Concept Schemes Route {#concept-schemes-route}

**ID**: `navigation.route.concept-schemes-route`

**Type**: `route`

Route for /app/concept-schemes — renders Concept Schemes View

#### Attributes

| Name | Value     |
| ---- | --------- |
| type | protected |

#### Relationships

| Type        | Related Element                | Predicate | Direction |
| ----------- | ------------------------------ | --------- | --------- |
| inter-layer | `ux.view.concept-schemes-view` | `maps-to` | outbound  |

### Configuration Route {#configuration-route}

**ID**: `navigation.route.configuration-route`

**Type**: `route`

Route serving the application configuration view

#### Attributes

| Name  | Value         |
| ----- | ------------- |
| title | Configuration |
| type  | public        |

#### Relationships

| Type        | Related Element                   | Predicate      | Direction |
| ----------- | --------------------------------- | -------------- | --------- |
| inter-layer | `ux.view.configuration-view`      | `maps-to`      | outbound  |
| intra-layer | `navigation.route.app-root-route` | `navigates-to` | inbound   |

### Datasets Route {#datasets-route}

**ID**: `navigation.route.datasets-route`

**Type**: `route`

Route for the dataset workspace management page — /app/datasets

#### Attributes

| Name  | Value    |
| ----- | -------- |
| title | Datasets |
| type  | public   |

#### Relationships

| Type        | Related Element                   | Predicate      | Direction |
| ----------- | --------------------------------- | -------------- | --------- |
| inter-layer | `ux.view.datasets-view`           | `maps-to`      | outbound  |
| intra-layer | `navigation.route.app-root-route` | `navigates-to` | inbound   |

### Individuals Route {#individuals-route}

**ID**: `navigation.route.individuals-route`

**Type**: `route`

Route for /app/individuals — renders Individuals View

#### Attributes

| Name | Value     |
| ---- | --------- |
| type | protected |

#### Relationships

| Type        | Related Element            | Predicate | Direction |
| ----------- | -------------------------- | --------- | --------- |
| inter-layer | `ux.view.individuals-view` | `maps-to` | outbound  |

### Interchange Route {#interchange-route}

**ID**: `navigation.route.interchange-route`

**Type**: `route`

Route for /app/interchange — renders Interchange View

#### Attributes

| Name | Value     |
| ---- | --------- |
| type | protected |

#### Relationships

| Type        | Related Element            | Predicate | Direction |
| ----------- | -------------------------- | --------- | --------- |
| inter-layer | `ux.view.interchange-view` | `maps-to` | outbound  |

### Properties Route {#properties-route}

**ID**: `navigation.route.properties-route`

**Type**: `route`

Route for /app/properties — renders Properties View

#### Attributes

| Name | Value     |
| ---- | --------- |
| type | protected |

#### Relationships

| Type        | Related Element           | Predicate | Direction |
| ----------- | ------------------------- | --------- | --------- |
| inter-layer | `ux.view.properties-view` | `maps-to` | outbound  |

### RAG Experiments Route {#rag-experiments-route}

**ID**: `navigation.route.rag-experiments-route`

**Type**: `route`

Route serving the RAG experiments and pipeline testing view

#### Attributes

| Name  | Value           |
| ----- | --------------- |
| title | RAG Experiments |
| type  | public          |

#### Relationships

| Type        | Related Element                              | Predicate      | Direction |
| ----------- | -------------------------------------------- | -------------- | --------- |
| inter-layer | `apm.metricinstrument.llm-execution-tracker` | `monitors`     | inbound   |
| inter-layer | `apm.metricinstrument.rag-processing-time`   | `monitors`     | inbound   |
| inter-layer | `ux.view.rag-experiments-view`               | `maps-to`      | outbound  |
| intra-layer | `navigation.route.app-root-route`            | `navigates-to` | inbound   |

### Relationships Route {#relationships-route}

**ID**: `navigation.route.relationships-route`

**Type**: `route`

Route for /app/relationships — renders Relationships View

#### Attributes

| Name | Value     |
| ---- | --------- |
| type | protected |

#### Relationships

| Type        | Related Element              | Predicate | Direction |
| ----------- | ---------------------------- | --------- | --------- |
| inter-layer | `ux.view.relationships-view` | `maps-to` | outbound  |

### Taxonomies Route {#taxonomies-route}

**ID**: `navigation.route.taxonomies-route`

**Type**: `route`

Route for /app/taxonomies — renders Taxonomies View

#### Attributes

| Name | Value     |
| ---- | --------- |
| type | protected |

#### Relationships

| Type        | Related Element           | Predicate | Direction |
| ----------- | ------------------------- | --------- | --------- |
| inter-layer | `ux.view.taxonomies-view` | `maps-to` | outbound  |

---

Generated: 2026-05-10T10:17:36.894Z | Model Version: 0.1.0

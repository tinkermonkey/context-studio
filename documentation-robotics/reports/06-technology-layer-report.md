# Technology

[← Back to README](../README.md)

Infrastructure, platforms, systems, and technology components.

## Report Index

- [Layer Introduction](#layer-introduction)
- [Intra-Layer Relationships](#intra-layer-relationships)
- [Inter-Layer Dependencies](#inter-layer-dependencies)
- [Inter-Layer Relationships Table](#inter-layer-relationships-table)
- [Element Reference](#element-reference)

## Layer Introduction

| Metric                    | Count |
| ------------------------- | ----- |
| Elements                  | 41    |
| Intra-Layer Relationships | 24    |
| Inter-Layer Relationships | 58    |
| Inbound Relationships     | 19    |
| Outbound Relationships    | 39    |

**Cross-Layer References**:

- **Upstream layers**: [APM](./12-apm-layer-report.md), [UX](./10-ux-layer-report.md)
- **Downstream layers**: [Application](./05-application-layer-report.md), [Motivation](./01-motivation-layer-report.md), [Security](./04-security-layer-report.md)

## Intra-Layer Relationships

*This layer has >30 elements. Summary table shown instead of diagram.*

| Element                                                             | Type                      | Relationships |
| ------------------------------------------------------------------- | ------------------------- | ------------- |
| `technology.communicationnetwork.localhost-lan`                     | `communicationnetwork`    | 1             |
| `technology.node.local-workstation`                                 | `node`                    | 1             |
| `technology.systemsoftware.alembic`                                 | `systemsoftware`          | 2             |
| `technology.systemsoftware.anthropic-sdk`                           | `systemsoftware`          | 1             |
| `technology.systemsoftware.axios`                                   | `systemsoftware`          | 0             |
| `technology.systemsoftware.boto3`                                   | `systemsoftware`          | 1             |
| `technology.systemsoftware.duck-db`                                 | `systemsoftware`          | 2             |
| `technology.systemsoftware.fast-api`                                | `systemsoftware`          | 2             |
| `technology.systemsoftware.git`                                     | `systemsoftware`          | 0             |
| `technology.systemsoftware.heimdall-ui`                             | `systemsoftware`          | 0             |
| `technology.systemsoftware.httpx`                                   | `systemsoftware`          | 1             |
| `technology.systemsoftware.mcp-python-sdk`                          | `systemsoftware`          | 0             |
| `technology.systemsoftware.network-x`                               | `systemsoftware`          | 1             |
| `technology.systemsoftware.open-telemetry-python-sdk`               | `systemsoftware`          | 0             |
| `technology.systemsoftware.open-telemetry-web-sdk`                  | `systemsoftware`          | 0             |
| `technology.systemsoftware.openai-sdk`                              | `systemsoftware`          | 1             |
| `technology.systemsoftware.pyarrow`                                 | `systemsoftware`          | 1             |
| `technology.systemsoftware.pydantic`                                | `systemsoftware`          | 1             |
| `technology.systemsoftware.pypdf`                                   | `systemsoftware`          | 0             |
| `technology.systemsoftware.python`                                  | `systemsoftware`          | 13            |
| `technology.systemsoftware.python-multipart`                        | `systemsoftware`          | 0             |
| `technology.systemsoftware.rdflib`                                  | `systemsoftware`          | 1             |
| `technology.systemsoftware.react`                                   | `systemsoftware`          | 3             |
| `technology.systemsoftware.reference-api-buddy`                     | `systemsoftware`          | 0             |
| `technology.systemsoftware.scikit-learn`                            | `systemsoftware`          | 0             |
| `technology.systemsoftware.sentence-transformers`                   | `systemsoftware`          | 1             |
| `technology.systemsoftware.spa-cy`                                  | `systemsoftware`          | 1             |
| `technology.systemsoftware.sqlalchemy`                              | `systemsoftware`          | 2             |
| `technology.systemsoftware.sqlite`                                  | `systemsoftware`          | 0             |
| `technology.systemsoftware.tailwind-css`                            | `systemsoftware`          | 1             |
| `technology.systemsoftware.tan-stack-form`                          | `systemsoftware`          | 0             |
| `technology.systemsoftware.tan-stack-query`                         | `systemsoftware`          | 1             |
| `technology.systemsoftware.tan-stack-router`                        | `systemsoftware`          | 1             |
| `technology.systemsoftware.tan-stack-table`                         | `systemsoftware`          | 0             |
| `technology.systemsoftware.trafilatura`                             | `systemsoftware`          | 0             |
| `technology.systemsoftware.uvicorn`                                 | `systemsoftware`          | 1             |
| `technology.systemsoftware.vite`                                    | `systemsoftware`          | 2             |
| `technology.systemsoftware.zustand`                                 | `systemsoftware`          | 0             |
| `technology.technologycollaboration.external-knowledge-integration` | `technologycollaboration` | 1             |
| `technology.technologyevent.rate-limit-threshold-event`             | `technologyevent`         | 2             |
| `technology.technologyinteraction.s3-sync-via-boto3`                | `technologyinteraction`   | 3             |

## Inter-Layer Dependencies

```mermaid
flowchart TB
  classDef current fill:#f9f,stroke:#333,stroke-width:2px
  motivation["Motivation"]
  business["Business"]
  product["Product"]
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
  apm --> technology
  technology --> application
  technology --> motivation
  technology --> security
  ux --> technology
  class technology current
```

## Inter-Layer Relationships Table

| Relationship ID                                                     | Source Node                                                           | Dest Node                                                                 | Dest Layer    | Predicate    | Cardinality  | Strength |
| ------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------- | ------------- | ------------ | ------------ | -------- |
| `apm.instrumentationconfig.monitors.technology.systemsoftware`      | `apm.instrumentationconfig.fast-api-sqlalchemy-httpx-instrumentation` | `technology.systemsoftware.fast-api`                                      | `technology`  | `monitors`   | many-to-many | medium   |
| `apm.instrumentationconfig.monitors.technology.systemsoftware`      | `apm.instrumentationconfig.fast-api-sqlalchemy-httpx-instrumentation` | `technology.systemsoftware.httpx`                                         | `technology`  | `monitors`   | many-to-many | medium   |
| `apm.instrumentationconfig.monitors.technology.systemsoftware`      | `apm.instrumentationconfig.fast-api-sqlalchemy-httpx-instrumentation` | `technology.systemsoftware.sqlalchemy`                                    | `technology`  | `monitors`   | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.alembic`                                   | `application.applicationcomponent.database-manager`                       | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.satisfies.motivation.constraint`         | `technology.systemsoftware.anthropic-sdk`                             | `motivation.constraint.external-llm-provider-required`                    | `motivation`  | `satisfies`  | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.anthropic-sdk`                             | `application.applicationcomponent.anthropic-chat-model`                   | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.anthropic-sdk`                             | `application.applicationcomponent.llm-provider-router`                    | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.boto3`                                     | `application.applicationcomponent.s3-sync-adapter`                        | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.duck-db`                                   | `application.applicationcomponent.duck-db-sync-adapter`                   | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.fast-api`                                  | `application.applicationcomponent.request-guard`                          | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.git`                                       | `application.applicationcomponent.dr-spec-reader`                         | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.httpx`                                     | `application.applicationcomponent.concept-net-reference-source`           | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.httpx`                                     | `application.applicationcomponent.dbpedia-reference-source`               | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.httpx`                                     | `application.applicationcomponent.http-page-fetcher`                      | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.httpx`                                     | `application.applicationcomponent.open-router-chat-model`                 | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.httpx`                                     | `application.applicationcomponent.open-router-llm-provider`               | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.httpx`                                     | `application.applicationcomponent.schema-org-reference-source`            | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.httpx`                                     | `application.applicationcomponent.wikidata-reference-source`              | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.mcp-python-sdk`                            | `application.applicationcomponent.mcp-server`                             | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.network-x`                                 | `application.applicationcomponent.network-x-graph-engine-adapter`         | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.open-telemetry-python-sdk`                 | `application.applicationcomponent.telemetry-lifecycle`                    | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.satisfies.motivation.constraint`         | `technology.systemsoftware.openai-sdk`                                | `motivation.constraint.external-llm-provider-required`                    | `motivation`  | `satisfies`  | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.openai-sdk`                                | `application.applicationcomponent.llm-provider-router`                    | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.pyarrow`                                   | `application.applicationcomponent.duck-db-sync-adapter`                   | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.pypdf`                                     | `application.applicationcomponent.pdf-text-reader`                        | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.python-multipart`                          | `application.applicationcomponent.local-source-file-store`                | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.satisfies.motivation.constraint`         | `technology.systemsoftware.python`                                    | `motivation.constraint.python-and-nodejs-runtime-versions`                | `motivation`  | `satisfies`  | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.rdflib`                                    | `application.applicationcomponent.rdflib-query-engine-adapter`            | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.satisfies.motivation.constraint`         | `technology.systemsoftware.reference-api-buddy`                       | `motivation.constraint.external-reference-source-rate-limits`             | `motivation`  | `satisfies`  | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.reference-api-buddy`                       | `application.applicationcomponent.cached-reference-source`                | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.scikit-learn`                              | `application.applicationcomponent.sklearn-clusterer`                      | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.sentence-transformers`                     | `application.applicationcomponent.sentence-transformer-embedding-adapter` | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.spa-cy`                                    | `application.applicationcomponent.sentence-transformer-embedding-adapter` | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.spa-cy`                                    | `application.applicationcomponent.spa-cy-nlp-processor`                   | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.realizes.security.countermeasure`        | `technology.systemsoftware.sqlalchemy`                                | `security.countermeasure.parameterized-queries-via-orm`                   | `security`    | `realizes`   | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.sqlalchemy`                                | `application.applicationcomponent.database-manager`                       | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.sqlalchemy`                                | `application.applicationcomponent.sqlite-ontology-repository`             | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.satisfies.motivation.constraint`         | `technology.systemsoftware.sqlite`                                    | `motivation.constraint.sqlite-only-persistence`                           | `motivation`  | `satisfies`  | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.sqlite`                                    | `application.applicationcomponent.database-manager`                       | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.serves.application.applicationcomponent` | `technology.systemsoftware.trafilatura`                               | `application.applicationcomponent.html-reader`                            | `application` | `serves`     | many-to-many | medium   |
| `technology.systemsoftware.satisfies.motivation.constraint`         | `technology.systemsoftware.uvicorn`                                   | `motivation.constraint.loopback-only-deployment`                          | `motivation`  | `satisfies`  | many-to-many | medium   |
| `technology.systemsoftware.satisfies.motivation.constraint`         | `technology.systemsoftware.vite`                                      | `motivation.constraint.python-and-nodejs-runtime-versions`                | `motivation`  | `satisfies`  | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.app-shell-view`                                              | `technology.systemsoftware.axios`                                         | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.app-shell-view`                                              | `technology.systemsoftware.heimdall-ui`                                   | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.app-shell-view`                                              | `technology.systemsoftware.open-telemetry-web-sdk`                        | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.app-shell-view`                                              | `technology.systemsoftware.react`                                         | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.app-shell-view`                                              | `technology.systemsoftware.tan-stack-query`                               | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.app-shell-view`                                              | `technology.systemsoftware.tan-stack-router`                              | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.app-shell-view`                                              | `technology.systemsoftware.zustand`                                       | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.class-drawer`                                                | `technology.systemsoftware.tan-stack-form`                                | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.command-palette`                                             | `technology.systemsoftware.heimdall-ui`                                   | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.grounding-workflow-drawer`                                   | `technology.systemsoftware.tan-stack-form`                                | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.individual-drawer`                                           | `technology.systemsoftware.tan-stack-form`                                | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.individuals-view`                                            | `technology.systemsoftware.tan-stack-table`                               | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.property-drawer`                                             | `technology.systemsoftware.tan-stack-form`                                | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.relationship-drawer`                                         | `technology.systemsoftware.tan-stack-form`                                | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.scheme-drawer`                                               | `technology.systemsoftware.tan-stack-form`                                | `technology`  | `depends-on` | many-to-many | medium   |
| `ux.view.depends-on.technology.systemsoftware`                      | `ux.view.taxonomy-drawer`                                             | `technology.systemsoftware.tan-stack-form`                                | `technology`  | `depends-on` | many-to-many | medium   |

## Element Reference

### Localhost LAN {#localhost-lan}

**ID**: `technology.communicationnetwork.localhost-lan`

**Type**: `communicationnetwork`

The local loopback network over which the React SPA communicates with the FastAPI back-end — standard localhost/127.0.0.1 HTTP

#### Attributes

| Name          | Value                                               |
| ------------- | --------------------------------------------------- |
| documentation | Localhost communication between UX and local-server |
| networkType   | lan                                                 |

#### Relationships

| Type        | Related Element                     | Predicate  | Direction |
| ----------- | ----------------------------------- | ---------- | --------- |
| intra-layer | `technology.node.local-workstation` | `connects` | outbound  |

### Local Workstation {#local-workstation}

**ID**: `technology.node.local-workstation`

**Type**: `node`

The user's own machine as the deployment target: it runs the FastAPI back end, the React SPA (the Vite dev server today, the Tauri desktop app soon) and the local SQLite workspace databases.

#### Attributes

| Name     | Value      |
| -------- | ---------- |
| nodeType | bare-metal |

#### Relationships

| Type        | Related Element                                 | Predicate  | Direction |
| ----------- | ----------------------------------------------- | ---------- | --------- |
| intra-layer | `technology.communicationnetwork.localhost-lan` | `connects` | inbound   |

### Alembic {#alembic}

**ID**: `technology.systemsoftware.alembic`

**Type**: `systemsoftware`

Database schema migration tool for SQLite — autogenerates migration scripts from SQLAlchemy ORM models for local.db and operations.db

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                     | Predicate    | Direction |
| ----------- | --------------------------------------------------- | ------------ | --------- |
| inter-layer | `application.applicationcomponent.database-manager` | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                  | `depends-on` | outbound  |
| intra-layer | `technology.systemsoftware.sqlalchemy`              | `depends-on` | outbound  |

### anthropic-sdk {#anthropic-sdk}

**ID**: `technology.systemsoftware.anthropic-sdk`

**Type**: `systemsoftware`

Official Anthropic Python client library used by the Anthropic LLM provider adapter to call Claude models.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                         | Predicate    | Direction |
| ----------- | ------------------------------------------------------- | ------------ | --------- |
| inter-layer | `motivation.constraint.external-llm-provider-required`  | `satisfies`  | outbound  |
| inter-layer | `application.applicationcomponent.anthropic-chat-model` | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.llm-provider-router`  | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                      | `depends-on` | outbound  |

### Axios {#axios}

**ID**: `technology.systemsoftware.axios`

**Type**: `systemsoftware`

Promise-based HTTP client used by the type-safe API layer for communicating with the FastAPI backend

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element          | Predicate    | Direction |
| ----------- | ------------------------ | ------------ | --------- |
| inter-layer | `ux.view.app-shell-view` | `depends-on` | inbound   |

### boto3 {#boto3}

**ID**: `technology.systemsoftware.boto3`

**Type**: `systemsoftware`

AWS SDK for Python. Used by the S3 sync adapter to push and pull DuckDB snapshot files to remote storage.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                    | Predicate    | Direction |
| ----------- | -------------------------------------------------- | ------------ | --------- |
| inter-layer | `application.applicationcomponent.s3-sync-adapter` | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                 | `depends-on` | outbound  |

### DuckDB {#duckdb}

**ID**: `technology.systemsoftware.duck-db`

**Type**: `systemsoftware`

In-process analytical SQL engine used by DuckDBSyncAdapter for serializing the local knowledge graph to Parquet format for remote sync

#### Attributes

| Name         | Value |
| ------------ | ----- |
| softwareType | dbms  |

#### Relationships

| Type        | Related Element                                         | Predicate    | Direction |
| ----------- | ------------------------------------------------------- | ------------ | --------- |
| inter-layer | `application.applicationcomponent.duck-db-sync-adapter` | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                      | `depends-on` | outbound  |
| intra-layer | `technology.systemsoftware.pyarrow`                     | `depends-on` | inbound   |

### FastAPI {#fastapi}

**ID**: `technology.systemsoftware.fast-api`

**Type**: `systemsoftware`

Python HTTP API framework — provides route declarations, dependency injection, and automatic OpenAPI spec generation for the backend

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                                       | Predicate    | Direction |
| ----------- | --------------------------------------------------------------------- | ------------ | --------- |
| inter-layer | `apm.instrumentationconfig.fast-api-sqlalchemy-httpx-instrumentation` | `monitors`   | inbound   |
| inter-layer | `application.applicationcomponent.request-guard`                      | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                                    | `depends-on` | outbound  |
| intra-layer | `technology.systemsoftware.uvicorn`                                   | `depends-on` | inbound   |

### git {#git}

**ID**: `technology.systemsoftware.git`

**Type**: `systemsoftware`

Git CLI, launched by the DR spec reader to read the spec checkout's source revision.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                   | Predicate | Direction |
| ----------- | ------------------------------------------------- | --------- | --------- |
| inter-layer | `application.applicationcomponent.dr-spec-reader` | `serves`  | outbound  |

### Heimdall UI {#heimdall-ui}

**ID**: `technology.systemsoftware.heimdall-ui`

**Type**: `systemsoftware`

@tinkermonkey/heimdall-ui design system: shell, navigation, inputs, overlays, data display, graph and chat components for the UX.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element           | Predicate    | Direction |
| ----------- | ------------------------- | ------------ | --------- |
| inter-layer | `ux.view.app-shell-view`  | `depends-on` | inbound   |
| inter-layer | `ux.view.command-palette` | `depends-on` | inbound   |

### httpx {#httpx}

**ID**: `technology.systemsoftware.httpx`

**Type**: `systemsoftware`

Async-capable HTTP client for Python. Used by the reference adapter and test infrastructure for making HTTP requests to external APIs and the FastAPI test client.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                                       | Predicate    | Direction |
| ----------- | --------------------------------------------------------------------- | ------------ | --------- |
| inter-layer | `apm.instrumentationconfig.fast-api-sqlalchemy-httpx-instrumentation` | `monitors`   | inbound   |
| inter-layer | `application.applicationcomponent.concept-net-reference-source`       | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.dbpedia-reference-source`           | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.http-page-fetcher`                  | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.open-router-chat-model`             | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.open-router-llm-provider`           | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.schema-org-reference-source`        | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.wikidata-reference-source`          | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                                    | `depends-on` | outbound  |

### MCP Python SDK {#mcp-python-sdk}

**ID**: `technology.systemsoftware.mcp-python-sdk`

**Type**: `systemsoftware`

Model Context Protocol server SDK (mcp) behind the /mcp endpoint.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                               | Predicate | Direction |
| ----------- | --------------------------------------------- | --------- | --------- |
| inter-layer | `application.applicationcomponent.mcp-server` | `serves`  | outbound  |

### NetworkX {#networkx}

**ID**: `technology.systemsoftware.network-x`

**Type**: `systemsoftware`

Python graph library (v3.1+) used by NetworkXGraphEngine adapter — provides directed graph construction, shortest path, centrality, and community detection algorithms

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                                   | Predicate    | Direction |
| ----------- | ----------------------------------------------------------------- | ------------ | --------- |
| inter-layer | `application.applicationcomponent.network-x-graph-engine-adapter` | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                                | `depends-on` | outbound  |

### OpenTelemetry Python SDK {#opentelemetry-python-sdk}

**ID**: `technology.systemsoftware.open-telemetry-python-sdk`

**Type**: `systemsoftware`

OpenTelemetry API/SDK, OTLP exporters and FastAPI/SQLAlchemy/httpx instrumentation for server traces and logs.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                        | Predicate | Direction |
| ----------- | ------------------------------------------------------ | --------- | --------- |
| inter-layer | `application.applicationcomponent.telemetry-lifecycle` | `serves`  | outbound  |

### OpenTelemetry Web SDK {#opentelemetry-web-sdk}

**ID**: `technology.systemsoftware.open-telemetry-web-sdk`

**Type**: `systemsoftware`

Browser tracing (sdk-trace-web, OTLP HTTP exporter) for the UX.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element          | Predicate    | Direction |
| ----------- | ------------------------ | ------------ | --------- |
| inter-layer | `ux.view.app-shell-view` | `depends-on` | inbound   |

### openai-sdk {#openai-sdk}

**ID**: `technology.systemsoftware.openai-sdk`

**Type**: `systemsoftware`

Official OpenAI Python client library used by the OpenAI LLM provider adapter to call GPT models.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                        | Predicate    | Direction |
| ----------- | ------------------------------------------------------ | ------------ | --------- |
| inter-layer | `motivation.constraint.external-llm-provider-required` | `satisfies`  | outbound  |
| inter-layer | `application.applicationcomponent.llm-provider-router` | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                     | `depends-on` | outbound  |

### pyarrow {#pyarrow}

**ID**: `technology.systemsoftware.pyarrow`

**Type**: `systemsoftware`

Apache Arrow columnar data format library used for Parquet file serialization in DuckDB-based remote sync operations

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                         | Predicate    | Direction |
| ----------- | ------------------------------------------------------- | ------------ | --------- |
| inter-layer | `application.applicationcomponent.duck-db-sync-adapter` | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.duck-db`                     | `depends-on` | outbound  |

### Pydantic {#pydantic}

**ID**: `technology.systemsoftware.pydantic`

**Type**: `systemsoftware`

Data validation library used exclusively in the adapter/web layer — Pydantic schemas define request and response shapes for all FastAPI routes

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                    | Predicate    | Direction |
| ----------- | ---------------------------------- | ------------ | --------- |
| intra-layer | `technology.systemsoftware.python` | `depends-on` | outbound  |

### pypdf {#pypdf}

**ID**: `technology.systemsoftware.pypdf`

**Type**: `systemsoftware`

PDF text extraction for PDF sources.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                    | Predicate | Direction |
| ----------- | -------------------------------------------------- | --------- | --------- |
| inter-layer | `application.applicationcomponent.pdf-text-reader` | `serves`  | outbound  |

### Python {#python}

**ID**: `technology.systemsoftware.python`

**Type**: `systemsoftware`

Primary backend runtime for local-server — all domain services, adapters, and API routes are implemented in Python 3.x

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                            | Predicate    | Direction |
| ----------- | ---------------------------------------------------------- | ------------ | --------- |
| inter-layer | `motivation.constraint.python-and-nodejs-runtime-versions` | `satisfies`  | outbound  |
| intra-layer | `technology.systemsoftware.alembic`                        | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.anthropic-sdk`                  | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.boto3`                          | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.duck-db`                        | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.fast-api`                       | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.httpx`                          | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.network-x`                      | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.openai-sdk`                     | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.pydantic`                       | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.rdflib`                         | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.sentence-transformers`          | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.spa-cy`                         | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.sqlalchemy`                     | `depends-on` | inbound   |

### python-multipart {#python-multipart}

**ID**: `technology.systemsoftware.python-multipart`

**Type**: `systemsoftware`

Python library providing multipart form data parsing, enabling FastAPI file upload endpoints for ontology import operations

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                            | Predicate | Direction |
| ----------- | ---------------------------------------------------------- | --------- | --------- |
| inter-layer | `application.applicationcomponent.local-source-file-store` | `serves`  | outbound  |

### RDFLib {#rdflib}

**ID**: `technology.systemsoftware.rdflib`

**Type**: `systemsoftware`

Python RDF library used by the graph adapter for RDF graph construction, SPARQL query execution, and ontology triple management

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                                | Predicate    | Direction |
| ----------- | -------------------------------------------------------------- | ------------ | --------- |
| inter-layer | `application.applicationcomponent.rdflib-query-engine-adapter` | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                             | `depends-on` | outbound  |

### React {#react}

**ID**: `technology.systemsoftware.react`

**Type**: `systemsoftware`

JavaScript UI library (v19.1) powering the Context Studio front-end — all UX components are React functional components with hooks

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                              | Predicate    | Direction |
| ----------- | -------------------------------------------- | ------------ | --------- |
| inter-layer | `ux.view.app-shell-view`                     | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.tan-stack-query`  | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.tan-stack-router` | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.vite`             | `depends-on` | inbound   |

### reference-api-buddy {#reference-api-buddy}

**ID**: `technology.systemsoftware.reference-api-buddy`

**Type**: `systemsoftware`

Caching HTTP proxy library behind the in-process reference proxy.

#### Attributes

| Name         | Value |
| ------------ | ----- |
| softwareType | cache |

#### Relationships

| Type        | Related Element                                               | Predicate   | Direction |
| ----------- | ------------------------------------------------------------- | ----------- | --------- |
| inter-layer | `motivation.constraint.external-reference-source-rate-limits` | `satisfies` | outbound  |
| inter-layer | `application.applicationcomponent.cached-reference-source`    | `serves`    | outbound  |

### scikit-learn {#scikit-learn}

**ID**: `technology.systemsoftware.scikit-learn`

**Type**: `systemsoftware`

Clustering and similarity utilities for the clusterer and embedding adapters.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                      | Predicate | Direction |
| ----------- | ---------------------------------------------------- | --------- | --------- |
| inter-layer | `application.applicationcomponent.sklearn-clusterer` | `serves`  | outbound  |

### sentence-transformers {#sentence-transformers}

**ID**: `technology.systemsoftware.sentence-transformers`

**Type**: `systemsoftware`

Python library providing pre-trained SentenceTransformer models — used by SentenceTransformerEmbedding adapter to generate semantic vector embeddings (default: all-MiniLM-L12-v2)

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                                           | Predicate    | Direction |
| ----------- | ------------------------------------------------------------------------- | ------------ | --------- |
| inter-layer | `application.applicationcomponent.sentence-transformer-embedding-adapter` | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                                        | `depends-on` | outbound  |

### spaCy {#spacy}

**ID**: `technology.systemsoftware.spa-cy`

**Type**: `systemsoftware`

Industrial-strength NLP library used by SpacyProcessor adapter for tokenization, named entity recognition, and linguistic feature extraction

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                                           | Predicate    | Direction |
| ----------- | ------------------------------------------------------------------------- | ------------ | --------- |
| inter-layer | `application.applicationcomponent.sentence-transformer-embedding-adapter` | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.spa-cy-nlp-processor`                   | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.python`                                        | `depends-on` | outbound  |

### SQLAlchemy {#sqlalchemy}

**ID**: `technology.systemsoftware.sqlalchemy`

**Type**: `systemsoftware`

Python ORM and SQL toolkit (v2.0+) used for all SQLite persistence — models, repositories, and connection management in local-server

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                                       | Predicate    | Direction |
| ----------- | --------------------------------------------------------------------- | ------------ | --------- |
| inter-layer | `apm.instrumentationconfig.fast-api-sqlalchemy-httpx-instrumentation` | `monitors`   | inbound   |
| inter-layer | `security.countermeasure.parameterized-queries-via-orm`               | `realizes`   | outbound  |
| inter-layer | `application.applicationcomponent.database-manager`                   | `serves`     | outbound  |
| inter-layer | `application.applicationcomponent.sqlite-ontology-repository`         | `serves`     | outbound  |
| intra-layer | `technology.systemsoftware.alembic`                                   | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.python`                                    | `depends-on` | outbound  |

### SQLite {#sqlite}

**ID**: `technology.systemsoftware.sqlite`

**Type**: `systemsoftware`

Embedded database engine for local.db, operations.db, reference.db and the reference cache, with sqlite-vec for vectors.

#### Attributes

| Name         | Value |
| ------------ | ----- |
| softwareType | dbms  |

#### Relationships

| Type        | Related Element                                     | Predicate   | Direction |
| ----------- | --------------------------------------------------- | ----------- | --------- |
| inter-layer | `motivation.constraint.sqlite-only-persistence`     | `satisfies` | outbound  |
| inter-layer | `application.applicationcomponent.database-manager` | `serves`    | outbound  |

### Tailwind CSS {#tailwind-css}

**ID**: `technology.systemsoftware.tailwind-css`

**Type**: `systemsoftware`

Utility-first CSS framework (v4.1) used for all frontend styling in the React UX

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                  | Predicate    | Direction |
| ----------- | -------------------------------- | ------------ | --------- |
| intra-layer | `technology.systemsoftware.vite` | `depends-on` | outbound  |

### TanStack Form {#tanstack-form}

**ID**: `technology.systemsoftware.tan-stack-form`

**Type**: `systemsoftware`

TanStack Form library used for type-safe form state management in Context Studio UX components

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                     | Predicate    | Direction |
| ----------- | ----------------------------------- | ------------ | --------- |
| inter-layer | `ux.view.class-drawer`              | `depends-on` | inbound   |
| inter-layer | `ux.view.grounding-workflow-drawer` | `depends-on` | inbound   |
| inter-layer | `ux.view.individual-drawer`         | `depends-on` | inbound   |
| inter-layer | `ux.view.property-drawer`           | `depends-on` | inbound   |
| inter-layer | `ux.view.relationship-drawer`       | `depends-on` | inbound   |
| inter-layer | `ux.view.scheme-drawer`             | `depends-on` | inbound   |
| inter-layer | `ux.view.taxonomy-drawer`           | `depends-on` | inbound   |

### TanStack Query {#tanstack-query}

**ID**: `technology.systemsoftware.tan-stack-query`

**Type**: `systemsoftware`

Server-state management library (v5.83) for the React UX — handles API data fetching, caching, and synchronization

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                   | Predicate    | Direction |
| ----------- | --------------------------------- | ------------ | --------- |
| inter-layer | `ux.view.app-shell-view`          | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.react` | `depends-on` | outbound  |

### TanStack Router {#tanstack-router}

**ID**: `technology.systemsoftware.tan-stack-router`

**Type**: `systemsoftware`

Type-safe file-based router (v1.116) for the React UX — manages all client-side navigation routes

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                   | Predicate    | Direction |
| ----------- | --------------------------------- | ------------ | --------- |
| inter-layer | `ux.view.app-shell-view`          | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.react` | `depends-on` | outbound  |

### TanStack Table {#tanstack-table}

**ID**: `technology.systemsoftware.tan-stack-table`

**Type**: `systemsoftware`

TanStack Table (formerly React Table) used for building data-intensive tables with sorting, filtering, and pagination in the Context Studio UX

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element            | Predicate    | Direction |
| ----------- | -------------------------- | ------------ | --------- |
| inter-layer | `ux.view.individuals-view` | `depends-on` | inbound   |

### trafilatura {#trafilatura}

**ID**: `technology.systemsoftware.trafilatura`

**Type**: `systemsoftware`

Main-text extraction from HTML pages for web sources.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                | Predicate | Direction |
| ----------- | ---------------------------------------------- | --------- | --------- |
| inter-layer | `application.applicationcomponent.html-reader` | `serves`  | outbound  |

### uvicorn {#uvicorn}

**ID**: `technology.systemsoftware.uvicorn`

**Type**: `systemsoftware`

ASGI server that serves the FastAPI application. Configured with standard extras for websocket and HTTP/2 support.

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                  | Predicate    | Direction |
| ----------- | ------------------------------------------------ | ------------ | --------- |
| inter-layer | `motivation.constraint.loopback-only-deployment` | `satisfies`  | outbound  |
| intra-layer | `technology.systemsoftware.fast-api`             | `depends-on` | outbound  |

### Vite {#vite}

**ID**: `technology.systemsoftware.vite`

**Type**: `systemsoftware`

Frontend build tool (v6.2) for the React UX — handles TypeScript compilation, hot module replacement, and production bundling

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element                                            | Predicate    | Direction |
| ----------- | ---------------------------------------------------------- | ------------ | --------- |
| inter-layer | `motivation.constraint.python-and-nodejs-runtime-versions` | `satisfies`  | outbound  |
| intra-layer | `technology.systemsoftware.tailwind-css`                   | `depends-on` | inbound   |
| intra-layer | `technology.systemsoftware.react`                          | `depends-on` | outbound  |

### Zustand {#zustand}

**ID**: `technology.systemsoftware.zustand`

**Type**: `systemsoftware`

Zustand lightweight state management library used for complex UI state in Context Studio React components

#### Attributes

| Name         | Value      |
| ------------ | ---------- |
| softwareType | middleware |

#### Relationships

| Type        | Related Element          | Predicate    | Direction |
| ----------- | ------------------------ | ------------ | --------- |
| inter-layer | `ux.view.app-shell-view` | `depends-on` | inbound   |

### External Knowledge Integration {#external-knowledge-integration}

**ID**: `technology.technologycollaboration.external-knowledge-integration`

**Type**: `technologycollaboration`

Technology collaboration between the reference adapter and external knowledge sources (ConceptNet, DBpedia, Wikidata, schema.org) coordinated by the reference adapter

#### Relationships

| Type        | Related Element                                      | Predicate     | Direction |
| ----------- | ---------------------------------------------------- | ------------- | --------- |
| intra-layer | `technology.technologyinteraction.s3-sync-via-boto3` | `assigned-to` | outbound  |

### Rate Limit Threshold Event {#rate-limit-threshold-event}

**ID**: `technology.technologyevent.rate-limit-threshold-event`

**Type**: `technologyevent`

Technology event fired when per-source request rate approaches the configured limit in config.json for external reference adapters (ConceptNet, DBpedia, Wikidata, schema.org)

#### Attributes

| Name          | Value                                                        |
| ------------- | ------------------------------------------------------------ |
| documentation | Per-source rate limit enforcement event in reference adapter |
| eventType     | threshold-breach                                             |

#### Relationships

| Type        | Related Element                                      | Predicate  | Direction |
| ----------- | ---------------------------------------------------- | ---------- | --------- |
| intra-layer | `technology.technologyinteraction.s3-sync-via-boto3` | `triggers` | outbound  |
| intra-layer | `technology.technologyinteraction.s3-sync-via-boto3` | `triggers` | inbound   |

### S3 Sync via boto3 {#s3-sync-via-boto3}

**ID**: `technology.technologyinteraction.s3-sync-via-boto3`

**Type**: `technologyinteraction`

Technology interaction in which the sync adapter serializes the local knowledge graph to Parquet format and uploads to S3 using boto3

#### Relationships

| Type        | Related Element                                                     | Predicate     | Direction |
| ----------- | ------------------------------------------------------------------- | ------------- | --------- |
| intra-layer | `technology.technologycollaboration.external-knowledge-integration` | `assigned-to` | inbound   |
| intra-layer | `technology.technologyevent.rate-limit-threshold-event`             | `triggers`    | inbound   |
| intra-layer | `technology.technologyevent.rate-limit-threshold-event`             | `triggers`    | outbound  |

---

Generated: 2026-11-19T16:49:39.982Z | Model Version: 0.1.0

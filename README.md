# Context Studio

Context Studio is a local-first application for building and curating knowledge graphs, and using those graphs for retrieval-augmented generation (RAG) and communication — with both humans and agents.

It gives you a workbench for turning unstructured source material into a structured, well-typed ontology: taxonomies, concept schemes, classes, and the typed relationships between them. Once curated, that graph becomes a grounded context layer — something an LLM pipeline can retrieve against instead of hallucinating structure on the fly, and something a human can browse and trust.

## Concept

Most RAG systems retrieve loose chunks of text and hope the LLM infers the relationships between them. Context Studio inverts that: the relationships *are* the data. Concepts are extracted from source material, matched or merged against existing entities using vector search over curated definitions (not just titles), and wired into an explicit ontology using standard knowledge-representation terms (`Taxonomy`, `ConceptScheme`, `Class`, `Relationship`, `ObjectProperty` — aligned with OWL/RDF/SKOS).

That process is split into two halves:

- **Curation** — a UI for humans to browse, edit, and approve the graph: creating classes, defining relationships, reviewing what extraction proposed.
- **Extraction** — an LLM/NLP pipeline that reads source documents, proposes new entities and relationships grounded in the existing graph, and hands them to curation for review.

Because everything is local-first, the graph, the models, and the pipeline configuration all live on the end user's machine — with optional remote sync for sharing or backup — rather than depending on a hosted service.

## Architecture

Context Studio is designed to be packaged as a desktop app (via Tauri) and run entirely on the end user's workstation.

```
/app                # Tauri v2 desktop shell — future packaging of /ux as a native app (not yet wired up)
/documentation       # Product documentation
/legacy              # REFERENCE ONLY — the previous implementation (frozen, not part of the active build)
/local-server        # Python back end for the desktop app (active greenfield build)
/rearchitecture       # Architecture design documents for the new back end
/ux                  # React front end for the desktop app (Vite build)
```

### Back end (`/local-server`)

- **Stack:** Python, FastAPI, SQLite (with SQLiteVector for embeddings), Alembic migrations, configurable LLM pipelines, remote sync via DuckDB + Parquet
- **Pattern:** Hexagonal architecture (ports & adapters) organized around six bounded contexts, each owning its own domain entities, ports, and use cases:
  1. **Ontology Management** — taxonomies, concept schemes, classes, relationships, property definitions
  2. **Graph Analysis** — in-memory graph construction, traversal, SPARQL, network metrics
  3. **Knowledge Extraction** — the RAG pipeline, NLP processing, external knowledge enrichment
  4. **LLM Pipeline Management** — pipeline configuration and execution tracking
  5. **Version Control & Collaboration** — change events, changesets, proposals, conflict resolution, sync
  6. **System Administration** — health, background tasks, configuration

The domain layer (`domain/`) has zero infrastructure imports — no FastAPI, no SQLAlchemy, no I/O — so business logic can be tested in isolation and infrastructure can be swapped without touching it. Persistence is split across three SQLite databases: `local.db` (the ontology workspace), `operations.db` (pipeline execution/background tasks), and cached/imported reference data pulled from sources like ConceptNet, DBpedia, and schema.org.

### Front end (`/ux`)

- **Stack:** React, TypeScript, Vite, Flowbite React, Tailwind CSS
- **State/data:** TanStack Router, Query, Table, and Form; a type-safe API client generated from the back end's OpenAPI spec
- **Design system:** built on `@tinkermonkey/heimdall-ui`, with a reference prototype under `ux/design/` used as the source of truth for new pages

The front end is built strictly after the corresponding back-end API is implemented and validated — API contracts and generated types come first, then hooks and services, then the UX workflows that use them.

## Status

The back end is an active greenfield rebuild replacing a frozen legacy implementation (kept under `/legacy` for reference only, with no backwards-compatibility requirement). The front end is being built out page by page against the new API as each capability lands on the back end.

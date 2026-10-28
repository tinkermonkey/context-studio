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

### Configuration (`local-server/config.json`)

The back end reads `local-server/config.json` (or the file `CONFIG_PATH` names). Each machine has its own copy, and git ignores it because it holds secrets: LLM API keys and the MCP token. On first start without one, the back end writes the defaults. To start from the repository's settings instead, copy `local-server/config.example.json` to `local-server/config.json` before the first start.

### MCP server (`/mcp`)

The running back end serves an MCP server at `/mcp`, so Claude Code and other MCP clients can read the workspace. It offers the same read-only tools as the in-app chat (`list_taxonomies`, `search_entities`, `get_entity`, and the list, neighbor and path tools), plus each taxonomy's vision statement as a markdown resource. Tool results include links to the entity pages in the app (base URL from `server.ui_base_url` in `config.json`; null turns links off).

Every request to `/mcp` needs a bearer token: without `Authorization: Bearer <token>` it gets a 401. On first start the back end generates the token and saves it as `mcp.auth_token` in `config.json`. To issue a new one, clear the value and restart; registered clients then need the new token.

To connect Claude Code, open **Settings → Integrations** in the app. It shows the token and a ready-to-paste command for this server's host and port:

```bash
claude mcp add --transport http context-studio http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer <token from Settings → Integrations>"
```

The server only starts when `server.host` is a loopback address. It also refuses requests whose `Host` or `Origin` header is not local, so a web page cannot reach it through the browser. The settings endpoint that hands the token to the UI (`GET /api/v1/admin/mcp`) is narrower still, and it does not rely on CORS. It only answers while the MCP server runs, to a loopback client under a loopback `Host` header. The request must also carry either no `Origin` header (same-origin and command-line callers) or the UI's own origin: `server.ui_base_url`, or an entry in `server.cors_origins` other than `*`.

### CORS and the REST API

`server.cors_origins` defaults to the UI origin (`server.ui_base_url`, `http://localhost:3100`), not `*`. If you open the UI at another origin, such as `http://127.0.0.1:3100`, add that origin to `server.cors_origins` in `config.json`.

**Residual risk:** the REST API (`/api/...`) is still unauthenticated. Anything that can reach the back end's port can read and change the workspace, including other processes on the same machine. CORS limits what other web pages can do in a browser; it is not authentication. Keep `server.host` on a loopback address.

## Status

The back end is an active greenfield rebuild replacing a frozen legacy implementation (kept under `/legacy` for reference only, with no backwards-compatibility requirement). The front end is being built out page by page against the new API as each capability lands on the back end.

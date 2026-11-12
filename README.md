# Context Studio

A local-first workbench for designing and curating an ontology: the taxonomies, classes, relationship types and individuals that describe a domain. Pipelines, the in-app chat, and agents connected over MCP all suggest changes. Every suggestion waits in one review queue with its rationale and evidence, and what you accept becomes the context that people browse and agents query.

**Agents propose. People decide. The graph becomes everyone's context.**

**→ [Read the field guide](https://tinkermonkey.github.io/context-studio/)** for the idea behind it, a worked example, and a guide to each area of the app with its MCP tools. This README covers getting it running.

## Quick start

You need Python 3.11 or later, Node.js 24, and an API key for Anthropic, OpenAI or OpenRouter.

1. **Install the back end.**

   ```bash
   cd local-server
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp config.example.json config.json
   ```

   Put your key in `config.json` under `llm`: `anthropic_api_key`, `openai_api_key` or `openrouter_api_key`. The file holds secrets, so git ignores it.

2. **Install the front end.**

   ```bash
   cd ux
   npm install
   ```

3. **Start both servers** from the repo root. `--migrate` creates or upgrades the databases.

   ```bash
   ./dev.sh --migrate
   ```

   The API runs on `:8000` and the UI on `:3100`. Open http://localhost:3100.

4. **Load something to look at.** On the empty Dashboard, choose **Load Demo Dataset › Software Architecture**, or **Create taxonomy** to start your own. Write the taxonomy's **Vision**: agents read it before they propose anything.

From here the field guide's [getting-started path](https://tinkermonkey.github.io/context-studio/#vision) takes you through growing the model from documents and running the review loop.

## Connect an agent (MCP)

The back end serves an MCP server at `http://127.0.0.1:8000/mcp`. Open **Configuration › Integrations** in the app for the token and a ready-to-paste command:

```bash
claude mcp add --transport http context-studio http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer <token from Configuration › Integrations>"
```

Agents can search and traverse the model, propose changes for review, add and extract sources, start refinement runs and submit claims. The [Agents guide](https://tinkermonkey.github.io/context-studio/#agents) lists all 26 tools.

The token is generated on first start and saved as `mcp.auth_token` in `config.json`. To rotate it, clear the value and restart. The MCP server only starts when `server.host` is a loopback address.

## Where to go next

| To… | Read |
| --- | --- |
| Understand the idea and see a worked example | [Vision](https://tinkermonkey.github.io/context-studio/#vision) |
| Design taxonomies, classes and relationship types | [Schema](https://tinkermonkey.github.io/context-studio/#schema) |
| Keep datasets apart and trace where facts came from | [Data](https://tinkermonkey.github.io/context-studio/#data) |
| Review, apply and revert changes | [Proposals](https://tinkermonkey.github.io/context-studio/#proposals) |
| Triage review notes | [Claims](https://tinkermonkey.github.io/context-studio/#claims) |
| Turn documents into cited facts | [Sources](https://tinkermonkey.github.io/context-studio/#sources) |
| Configure and audit LLM pipelines | [Pipelines](https://tinkermonkey.github.io/context-studio/#pipelines) |
| Explore the graph and ask questions | [Graph & chat](https://tinkermonkey.github.io/context-studio/#explore) |
| See what works today and what's planned | [Where it stands](https://tinkermonkey.github.io/context-studio/#vision) |

## Repository layout

```
/local-server     Python back end: FastAPI, SQLite, Alembic, LLM pipelines, MCP server
/ux               React front end (Vite, TanStack, Heimdall design system)
/documentation    Product documentation, including the field guide's source
/rearchitecture   Design documents for the back end
/app              Tauri desktop shell, not yet wired up
/legacy           The previous implementation, frozen, for reference only
```

The back end follows a hexagonal (ports and adapters) design; `domain/` has no infrastructure imports. See [architecture_design.md](rearchitecture/architecture_design.md) and the [ontology workbench proposal](rearchitecture/ontology_workbench_proposal.md). [CLAUDE.md](CLAUDE.md) holds the working conventions for contributors and agents.

## Development

```bash
# Back end (from local-server/)
.venv/bin/pytest tests/unit -q
.venv/bin/python scripts/check_domain_imports.py

# Front end (from ux/)
npm run typecheck
npm test
```

When the API changes, run `local-server/scripts/update_api_specs.py`, then `npm run generate-types` in `ux/`.

The field guide is a single HTML page at [documentation/field-guide/index.html](documentation/field-guide/index.html). A push to `main` that changes it republishes the site.

## Configuration and security

The back end reads `local-server/config.json`, or the file `CONFIG_PATH` names. Without one, it writes the defaults on first start.

Only the app's own UI may call the API from a browser. The allowed origins are the origin of `server.ui_base_url` (`http://localhost:3100` by default) plus each entry in `server.cors_origins`. If you open the UI at another origin, such as `http://127.0.0.1:3100` or a Tauri build, add that origin to `server.cors_origins`. A `*` entry is ignored. The back end refuses (403) browser requests from any other origin and, while it listens on loopback, requests with a non-local `Host` header.

**Residual risk:** the REST API itself has no login. Anything that can reach the back end's port can read and change the workspace, including other processes on the same machine. Keep `server.host` on a loopback address. The Vite dev server listens on every network interface and proxies `/api`, so while `npm run dev` runs, other machines on your network can reach the API through port 3100, including the endpoint that returns the MCP token.

## Status

Active development. The back end is a greenfield rebuild; the front end is built page by page as each capability lands. The field guide's [Where it stands](https://tinkermonkey.github.io/context-studio/#vision) section lists what works today, what's in progress and what's planned, and [#1322](https://github.com/tinkermonkey/context-studio/issues/1322) tracks open work.

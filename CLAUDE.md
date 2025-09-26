# Context Studio

Context Studio is a local-first application for creating and curating knowledge graphs, and using those graphs for RAG and communication for both humans and agents.

## Mission Statement

**Critical:** Your purpose is to guide the definition of cross-function requirements and to provide cross-functional debugging. Software development takes place in the sub-directories. For requirements definition you are not expected to create code beyond example implementation and design. Function like an expert product manager and software architect for design work.

For cross-functional troubleshooting, use your access to the codebases to guide your designs and your troubleshooting. Ensure that the front-end and back-end are interfacing correctly.

### Change management

Typically functionality is build in the back-end first, tested and validated, and then the ux for that functionality is built.

When back-end APIs are added / updated / removed, the utility script `/local-server/utils/update_api_specs.py` is used to update the `openapi.json` file for both the back end and the front end. Once that file is updated the front-end should execute the `npm run generate-types` command to update the digested view of the apis and types. After that is done, the hooks and services should be updated, and only after that is complete the user experience and user workflows can be built out using those hooks and services.

### Change documentation

Use GitHub issues for change documentation and GitHub issue tasks for task management.

When creating a PRP, it should be a new GitHub issue.

When executing a PRP, create tasks linked to the parent issue and keep them up to date.

## Architecture

Context studio is local-first meaning its designed to be packaged as a desktop app and run locally on end-user workstations.

- **Back End:** Python, sqlite, configurable llm pipelines, remote sync via duckdb & parquet

- **Front End:** React, flowbite-react

- **Desktop App:** Tauri builds for MacOS, Windows, Linux, iOS & Android tablets, maybe phones some day

- **Connected:** Eventually function as an MCP server, provide a chat bridge service for deploying expert agents to business chat platforms, RAG service, embedded co-reading via tauri browser views

## Repo Structure

```
/agent              # Future chat-with-graph-data agent
/app                # Tauri app definition
/documentation      # Product documentation
/local-server       # python back-end for the desktop app
/ux                 # react front-end for the desktop app (vite build)
```

## Development Status

- **Back End:**
  - Nearing beta stage
  - Under very active development adding new features and functionality
  - Decent error handling / scaling / maturity
  - Functionality present:
    - Basic CRUD for core knowledge graph structure dataset
    - Change tracking for knowledge graph structure dataset
    - Dataset management (multiple local DB files)
    - Basic LLM pipelines with tracking
    - Basic monitoring & metrics
    - NLP tooling
    - Reference dataset tooling
  - Functionality not started:
    - Knowledge graph data instances mapped to structure
    - Chat with data
    - RAG pipelines
    - MCP server

- **Front End:**
  - Neading beta stage
  - Under very active development adding new features and functionality in sync with back-end
  - Reasonably user navigation, POC functionality is in place
  - Functionality present:
    - Basic CRUD for core knowledge graph structure dataset
    - LLM pipeline invocation & monitoring
    - Dataset management
  - Functionality not started:
    - Complex context merging & analysis
    - Co-browsing with RAG
    - Chat with data interface

- **Desktop App:**
  - Not started

- **Business Chat Bridge:**
  - Not started

## Core Principles

**IMPORTANT: You MUST follow these principles in all code changes and PRP generations:**

### KISS (Keep It Simple, Stupid)

- Simplicity should be a key goal in design
- Choose straightforward solutions over complex ones whenever possible
- Simple solutions are easier to understand, maintain, and debug

### YAGNI (You Aren't Gonna Need It)

- Avoid building functionality on speculation
- Implement features only when they are needed, not when you anticipate they might be useful in the future

# Context Studio

Context Studio is a local-first application for creating and curating knowledge graphs, and using those graphs for RAG and communication for both humans and agents.

### Change management

Typically functionality is build in the back-end first, tested and validated, and then the ux for that functionality is built.

When back-end APIs are added / updated / removed, the utility script `/local-server/utils/update_api_specs.py` is used to update the `openapi.json` file for both the back end and the front end. Once that file is updated the front-end should execute the `npm run generate-types` command to update the digested view of the apis and types. After that is done, the hooks and services should be updated, and only after that is complete the user experience and user workflows can be built out using those hooks and services.

## Architecture

Context studio is local-first meaning its designed to be packaged as a desktop app and run locally on end-user workstations.

- **Back End:** Python, sqlite, configurable llm pipelines, remote sync via duckdb & parquet

- **Front End:** React, flowbite-react

## Repo Structure

```
/documentation      # Product documentation
/local-server       # python back-end for the desktop app
/ux                 # react front-end for the desktop app (vite build)
```

## Core Principles

**IMPORTANT: You MUST follow these principles in all code changes:**

- Do not create documentation files unless explicitly asked to do so

### KISS (Keep It Simple, Stupid)

- Simplicity should be a key goal in design
- Choose straightforward solutions over complex ones whenever possible
- Simple solutions are easier to understand, maintain, and debug

### YAGNI (You Aren't Gonna Need It)

- Avoid building functionality on speculation
- Implement features only when they are needed, not when you anticipate they might be useful in the future

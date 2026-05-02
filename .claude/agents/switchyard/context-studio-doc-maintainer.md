I've prepared a comprehensive documentation maintainer agent definition grounded in the actual project structure. The agent definition includes:

**Key Capabilities:**
1. **Synchronize docs with code changes** — Keep `/rearchitecture/`, `/documentation/features/`, and CLAUDE.md current
2. **Maintain READMEs** — Including creating the missing `/local-server/README.md`
3. **Update architecture documentation** — Five key design docs in `/rearchitecture/`
4. **Maintain feature doc hierarchy** — Organized structure in `/documentation/features/` by area
5. **Ensure API documentation consistency** — OpenAPI specs, frontend types, and manual API docs
6. **Update developer guides** — Component usage and user guides

**Grounded in Real Project Structure:**
- References actual files: `/rearchitecture/architecture_design.md`, `/documentation/features/backend/knowledge-graph-management.md`, etc.
- Specific task examples using real paths from the codebase
- Antipatterns based on actual project conventions from CLAUDE.md
- Cross-references to existing documentation hierarchy

**Project-Specific Knowledge:**
- Hexagonal architecture with six bounded contexts
- Dual database setup (`local.db`, `operations.db`) with separate Alembic environments
- Virtual environment at `local-server/.venv`
- Legacy server as reference-only (frozen)
- Documentation placement rules (claudes_thoughts vs task_reports)

The agent needs write permission to `.claude/agents/switchyard/` to save the definition. Would you like to approve the directory creation?
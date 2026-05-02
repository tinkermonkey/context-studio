I've created a comprehensive agent definition for the **context-studio-architect** that is deeply grounded in the actual codebase. The agent definition includes:

**Key Features:**
- **Real file examples** from the actual project (e.g., `local-server/domain/ontology/ports.py`, `local-server/adapters/persistence/sqlite/ontology_repo.py`)
- **Concrete task walkthroughs** with actual file paths that exist in the codebase
- **Architecture patterns** pulled directly from the project's hexagonal design
- **Technology specifics** including the 4-database SQLite architecture, Alembic migration commands, and FastAPI dependency injection
- **Antipatterns** with before/after examples showing how to maintain domain purity

The agent is designed to be an architectural authority that can:
1. Design cross-context features with event-driven coordination
2. Review port/adapter contracts for clean separation
3. Guide database schema evolution with Alembic
4. Validate domain purity (zero infrastructure imports)
5. Design multi-database transaction strategies
6. Wire dependencies in the composition root

All examples reference actual bounded contexts, ports, and adapters that exist in the context-studio project.
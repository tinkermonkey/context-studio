The agent definition is ready. I've created a comprehensive data expert agent that covers:

**Core Expertise:**
- Dual-database architecture (local.db + operations.db)
- SQLAlchemy ORM modeling with single-table inheritance pattern
- Alembic migration management with separate environments
- Domain-to-ORM mapping layer
- Repository pattern implementation

**Grounded in Real Code:**
- OntologyEntity model from `models.py` (unified table with discriminator)
- Mapper functions from `mappers.py` (domain ↔ ORM translation)
- Repository pattern from `ontology_repo.py`
- Actual migration files from `versions/`

**Practical Capabilities:**
- Schema evolution with concrete examples
- Migration generation and rollback procedures
- Repository method implementation
- Integration testing patterns

**Critical Guidelines:**
- Never hand-write migration SQL (always autogenerate)
- Domain uses dataclasses, not SQLAlchemy
- UUID comparison requires string casting for SQLite
- Always run commands from `local-server/` directory
- Must specify `--version-path` when generating migrations

The agent definition includes antipatterns to avoid and common task examples using actual file paths from the project.
---
name: context-studio-data-expert
description: Database and persistence specialist for Context Studio. Expert in the dual-database SQLite setup, SQLAlchemy ORM models, Alembic migrations, and the repository pattern. Use for schema changes, migration generation, repository implementation, and data layer debugging.
tools: Bash, Read, Edit, Glob, Grep
---

# Context Studio Data Expert

## Database architecture

Two Alembic-managed databases, two unmanaged reference databases:

| Database | Path | Managed by |
|----------|------|------------|
| `local.db` | `local-server/local.db` | Alembic (`versions/`) |
| `operations.db` | `local-server/operations.db` | Alembic (`operations/versions/`) |
| `reference_api_cache.db` | `local-server/reference_api_cache.db` | None — drop and rebuild |
| `reference.db` | `local-server/reference.db` | None — drop and rebuild |

**Never run migrations on reference databases.** They have no Alembic history.

## ORM models (source of truth)

SQLAlchemy ORM models are the **single source of truth** for schema. Never hand-write DDL or migration SQL.

- `local.db` models: `local-server/adapters/persistence/sqlite/models.py`
- `operations.db` models: `local-server/adapters/persistence/sqlite/operations/models.py`

The `ontology_entities` table uses **single-table inheritance** with `node_type` as discriminator. All entity types (Taxonomy, ConceptScheme, Class, Individual) share one table.

## Migration workflow

Always run from `local-server/` with venv activated. Use `python -m alembic` (not bare `alembic`):

```bash
cd local-server && source .venv/bin/activate

# Generate migration for local.db
python -m alembic --config adapters/persistence/sqlite/alembic.ini \
  revision --autogenerate \
  --version-path adapters/persistence/sqlite/versions \
  -m "describe the change"

# Apply local.db migrations
python -m alembic --config adapters/persistence/sqlite/alembic.ini upgrade head

# Generate migration for operations.db
python -m alembic --config adapters/persistence/sqlite/alembic.ini \
  -x db=operations revision --autogenerate \
  --version-path adapters/persistence/sqlite/operations/versions \
  -m "describe the change"

# Apply operations.db migrations
python -m alembic --config adapters/persistence/sqlite/alembic.ini -x db=operations upgrade head

# Rollback
python -m alembic --config adapters/persistence/sqlite/alembic.ini downgrade -1
```

**The `--version-path` flag is required** when using multiple `version_locations`. Omitting it causes Alembic to write the migration to the wrong directory.

## Repository pattern

Repositories in `adapters/persistence/sqlite/` translate between domain entities (dataclasses) and ORM models. The domain never sees SQLAlchemy:

```python
# Domain entity — pure dataclass
@dataclass
class Taxonomy:
    id: str
    title: str

# ORM model — SQLAlchemy, adapter layer only
class OntologyEntity(Base):
    __tablename__ = "ontology_entities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    node_type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)

# Repository — maps between the two
class SQLiteOntologyRepository:
    def get_taxonomy(self, taxonomy_id: str) -> Optional[Taxonomy]:
        orm = self.session.query(OntologyEntity).filter(
            OntologyEntity.id == str(taxonomy_id),  # cast UUID to str
            OntologyEntity.node_type == NodeType.TAXONOMY.value
        ).first()
        return self._to_taxonomy(orm) if orm else None
```

**UUID pitfall:** SQLite stores UUIDs as text. Always cast UUID values to `str()` in filter conditions: `OntologyEntity.id == str(taxonomy_id)`.

## Schema change checklist

1. Edit the ORM model in `models.py`
2. Generate the migration (`revision --autogenerate`)
3. Review the generated script in `versions/` — confirm it reflects the intended change
4. Apply the migration (`upgrade head`)
5. Run integration tests to confirm: `pytest tests/integration/`
6. If rolling back: `downgrade -1`, then fix the model and regenerate

## SQLiteVector

Embedding columns use the `SQLiteVector` extension. The `embedding` column stores dense float vectors. When adding embedding support to a new entity type, follow the pattern in the existing `OntologyEntity` model for the `embedding` and `is_indexed` columns.

## Antipatterns

- Hand-writing SQL in migration files — always autogenerate, then review
- Importing ORM models into `domain/` — ORM belongs in `adapters/persistence/sqlite/` only
- Comparing UUID fields without `str()` cast — always cast
- Running `alembic` without activating the venv — `python -m alembic` is the safe form
- Omitting `--version-path` when running autogenerate with multiple version locations
- Applying migrations to reference databases (`reference.db`, `reference_api_cache.db`)

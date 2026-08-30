"""
Build the in-memory ontology + schema vector index the quality loop grounds against.

The individual-extraction quality scenarios reference a source ontology by
identifier in each fixture's `ontology_id` (the DR-spec scenarios use
`dr_spec`; the legacy placeholder scenarios use a stale test id that resolves
to nothing). Loop A/B evaluates the open_v1 grounding stage against that
ontology, so the harness needs a real `SchemaVectorIndex` — not `None`, which
made the grounding knobs inert (karpathy_loop_dr_ontology_design.md §4).

This builds ONE in-memory `local.db` holding both the throwaway placeholder
ontology and (when the sibling `documentation_robotics/spec` checkout is
present) the full imported DR spec, then a single `SqliteSchemaVectorIndex`
over it. Per-scenario scoping to the right taxonomy is the orchestrator's job
(it resolves `ontology_id` to a taxonomy and passes `taxonomy_id` to search),
so one shared index serves every scenario. In-memory rather than the on-disk
`local.db` on purpose: a baseline-resetting loop must be deterministic and
CI-reproducible, and the on-disk workspace carries mutable, environment-specific
rows.

If the DR spec checkout is absent, the DR half is omitted and the DR scenarios'
`dr_spec` identifier resolves to nothing, so grounding self-skips for them —
the loop degrades to its pre-DR behavior with no hard dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import uuid4

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.ontology.ports import EmbeddingService, OntologyRepository
from domain.ontology.services import OntologyService
from scripts.dr_ontology_loader import import_dr_ontology
from scripts.import_dr_ontology import DEFAULT_SPEC_DIR

# Fallback location for the sibling `documentation_robotics/spec` checkout in
# container environments; DEFAULT_SPEC_DIR (the sibling checkout) is preferred.
_SPEC_DIR_FALLBACK = Path("/reference/documentation_robotics/spec")


def find_dr_spec_dir() -> Path | None:
    """The DR spec checkout if one is present on this machine, else None."""
    for candidate in (DEFAULT_SPEC_DIR, _SPEC_DIR_FALLBACK):
        if candidate.is_dir():
            return candidate
    return None


def _insert_placeholder_ontology(repo: SQLiteOntologyRepository) -> None:
    """The throwaway 3-class (individual/property/entity) ontology."""
    tax = Taxonomy(
        id=str(uuid4()),
        identifier="placeholder",
        title="Placeholder Ontology",
        description="Throwaway 3-class ontology for individual-extraction quality tests",
    )
    repo.save_taxonomy(tax)
    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="placeholder_scheme",
        taxonomy_id=tax.id,
        title="Placeholder Scheme",
        description="Placeholder concept scheme",
    )
    repo.save_concept_scheme(scheme)
    for class_name in ("individual", "property", "entity"):
        repo.save_class(
            Class(
                id=str(uuid4()),
                identifier=class_name,
                concept_scheme_id=scheme.id,
                taxonomy_id=tax.id,
                title=class_name.title(),
                description=f"A {class_name}",
            )
        )


def build_eval_ontology(
    embedding_service: EmbeddingService,
) -> tuple[SQLiteOntologyRepository, SqliteSchemaVectorIndex]:
    """
    An in-memory ontology repository + reindexed schema vector index for the loop.

    The index is embedded with the SAME `embedding_service` the orchestrator
    queries with, so query and stored vectors are comparable. The DR spec is
    included when its checkout is found; the placeholder ontology is always
    present so taxonomy scoping is exercised against a multi-ontology workspace.
    """
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)

    _insert_placeholder_ontology(repo)

    spec_dir = find_dr_spec_dir()
    if spec_dir is not None:
        # schema_index=None here suppresses per-entity embedding sync during the
        # bulk import; the single reindex_all() below populates every vector once.
        ontology_service = OntologyService(
        repository=cast(OntologyRepository, repo),
            embedding_service=embedding_service,
            event_publisher=InProcessEventPublisher(),
            schema_index=None,
        )
        import_dr_ontology(ontology_service, cast(OntologyRepository, repo), spec_dir)

    index = SqliteSchemaVectorIndex(session_factory, embedding_service)
    index.reindex_all()
    return repo, index

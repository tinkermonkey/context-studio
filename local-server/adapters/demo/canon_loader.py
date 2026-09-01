"""
Canon-backed implementation of the DemoDatasetLoader port.

Reads a curated ontology slice from a directory of JSON files and materializes it
through the SQLiteOntologyRepository's existing save_* methods. No LLM calls,
no network access — the demo is offline and deterministic.

Layout of a canon directory:
- canon.json           — master slice with taxonomies, concept_schemes,
                         class_hierarchy, property_definitions
- paper_<slug>.json    — per-paper fixtures (optional) used here for
                         expected_external_refs attached to classes

Idempotency policy: if the dataset's root taxonomy already exists (matched by
slug `identifier`), the loader raises DemoDatasetAlreadyLoadedError rather than
attempt to merge. Users wanting a clean load should delete the existing taxonomy
or use a fresh database.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from pathlib import Path
from types import MappingProxyType
from typing import Any

from domain.admin.exceptions import (
    DemoDatasetAlreadyLoadedError,
    DemoDatasetMalformedError,
    DemoDatasetNotFoundError,
)
from domain.admin.value_objects import DemoDatasetDescriptor, LoadResult
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import (
    ExternalReference,
    LexicalSense,
    Status,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# Hand-maintained registry of canon-backed demo datasets. Explicit beats clever:
# adding a dataset requires an entry here AND a directory under canon_root.
_DATASETS: dict[str, dict[str, str]] = {
    "software-architecture": {
        "directory": "software_architecture",
        "title": "Software Architecture",
        "description": (
            "A curated taxonomy of software-architecture concepts drawn from "
            "canonical sources (Fielding's REST dissertation, Lamport's clocks "
            "and Paxos, Brewer's CAP keynote, Shapiro's CRDT survey, Fowler's "
            "microservices and CQRS, Evans' DDD, Hohpe & Woolf's EIP, and the "
            "Bass/Clements/Kazman quality-attributes work). Spans architectural "
            "styles, constraints, consistency models, consensus protocols, "
            "replication strategies, integration patterns, and quality attributes."
        ),
    },
}


class CanonDemoDatasetLoader:
    """
    Loads a canon-backed demo dataset into the ontology repository.

    Attributes:
        canon_root: Filesystem directory containing one subdirectory per dataset.
        ontology_repo: Repository used to persist taxonomies, schemes, classes,
            property definitions, individuals, and relationships.
    """

    def __init__(
        self,
        canon_root: Path,
        ontology_repo: OntologyRepository,
    ) -> None:
        """
        Initialize the loader.

        Args:
            canon_root: Path to the canon directory containing per-dataset folders.
            ontology_repo: Repository used to persist ontology entities.
        """
        self._canon_root = Path(canon_root)
        self._repo = ontology_repo

    # ------------------------------------------------------------------ #
    # Port surface                                                        #
    # ------------------------------------------------------------------ #

    def list_available(self) -> tuple[DemoDatasetDescriptor, ...]:
        """
        List demo datasets registered in the hand-maintained registry.

        Returns:
            Tuple of DemoDatasetDescriptor for each dataset whose directory exists.
        """
        descriptors: list[DemoDatasetDescriptor] = []
        for name, meta in _DATASETS.items():
            dataset_dir = self._canon_root / meta["directory"]
            if not (dataset_dir / "canon.json").is_file():
                logger.warning(
                    "Demo dataset '%s' is registered but canon.json is missing in %s",
                    name,
                    dataset_dir,
                )
                continue

            canon = self._read_canon(dataset_dir)
            paper_count = len(list(dataset_dir.glob("paper_*.json")))
            taxonomy_count = len(canon.get("taxonomies", []))
            class_count = len(canon.get("class_hierarchy", []))
            descriptors.append(
                DemoDatasetDescriptor(
                    name=name,
                    title=meta["title"],
                    description=meta["description"],
                    paper_count=paper_count,
                    taxonomy_count=taxonomy_count,
                    class_count=class_count,
                )
            )
        return tuple(descriptors)

    def load(self, name: str, run_id: str) -> LoadResult:
        """
        Materialize the named dataset into the ontology repository.

        Args:
            name: Stable dataset identifier.
            run_id: Provenance id stamped on every persisted entity.

        Returns:
            LoadResult with counts of each persisted entity type.

        Raises:
            DemoDatasetNotFoundError: if `name` is not registered.
            DemoDatasetAlreadyLoadedError: if any taxonomy in the dataset is
                already present in the database (matched by slug identifier).
            DemoDatasetMalformedError: if the canon JSON has structural defects
                (dangling parent references, cyclic hierarchy, scheme pointing
                at an unknown taxonomy, etc.).
        """
        if name not in _DATASETS:
            raise DemoDatasetNotFoundError(name)

        try:
            return self._perform_load(name, run_id)
        except (DemoDatasetNotFoundError, DemoDatasetAlreadyLoadedError):
            # Preserve typed domain failures verbatim.
            raise
        except ValueError as exc:
            # Convert canon-integrity errors into a typed domain exception so
            # the route layer maps them to 422 rather than an opaque 500.
            raise DemoDatasetMalformedError(name=name, reason=str(exc)) from exc

    def _perform_load(self, name: str, run_id: str) -> LoadResult:
        """Inner load body. Raises domain exceptions; ValueError is wrapped by load()."""
        dataset_dir = self._canon_root / _DATASETS[name]["directory"]
        canon = self._read_canon(dataset_dir)
        papers = self._read_papers(dataset_dir)

        # ---- Pre-flight: idempotency check ---------------------------------- #
        for tax in canon.get("taxonomies", []):
            existing = self._repo.get_by_identifier(tax["identifier"])
            if existing is not None:
                raise DemoDatasetAlreadyLoadedError(name)

        # ---- Step 1: Taxonomies -------------------------------------------- #
        taxonomy_slug_to_id: dict[str, str] = {}
        for tax in canon.get("taxonomies", []):
            domain_tax = Taxonomy(
                id=str(uuid.uuid4()),
                identifier=tax["identifier"],
                title=tax["title"],
                description=tax.get("description"),
                color=tax.get("color"),
                status=self._coerce_status(tax.get("status")),
            )
            saved = self._repo.save_taxonomy(domain_tax)
            assert saved.identifier is not None
            taxonomy_slug_to_id[saved.identifier] = saved.id

        # ---- Step 2: Concept schemes --------------------------------------- #
        scheme_slug_to_id: dict[str, str] = {}
        scheme_slug_to_taxonomy_id: dict[str, str] = {}
        for scheme in canon.get("concept_schemes", []):
            tax_slug = scheme["taxonomy_identifier"]
            tax_id = taxonomy_slug_to_id.get(tax_slug)
            if tax_id is None:
                raise ValueError(
                    f"Concept scheme '{scheme['identifier']}' references unknown "
                    f"taxonomy '{tax_slug}'"
                )
            domain_scheme = ConceptScheme(
                id=str(uuid.uuid4()),
                taxonomy_id=tax_id,
                identifier=scheme["identifier"],
                title=scheme["title"],
                description=scheme.get("description"),
                color=scheme.get("color"),
                status=self._coerce_status(scheme.get("status")),
            )
            saved_scheme = self._repo.save_concept_scheme(domain_scheme)
            assert saved_scheme.identifier is not None
            scheme_slug_to_id[saved_scheme.identifier] = saved_scheme.id
            scheme_slug_to_taxonomy_id[saved_scheme.identifier] = tax_id

        # ---- Step 3: Property definitions ---------------------------------- #
        property_defs_count = 0
        for prop in canon.get("property_definitions", []):
            domain_prop = PropertyDefinition(
                id=str(uuid.uuid4()),
                identifier=prop["identifier"],
                title=prop["title"],
                description=prop.get("description"),
                lexical_senses=self._coerce_lexical_senses(prop.get("lexical_senses")),
                status=Status.PUBLISHED,
                source_run_id=run_id,
            )
            self._repo.save_property_definition(domain_prop)
            property_defs_count += 1

        # ---- Step 4: Classes (topologically sorted by parent_class_identifier) #
        external_refs_by_class_slug = self._collect_external_refs(papers)

        sorted_classes = self._topological_sort_classes(canon.get("class_hierarchy", []))
        class_slug_to_id: dict[str, str] = {}
        external_refs_attached = 0
        for cls_data in sorted_classes:
            scheme_slug = cls_data["concept_scheme_identifier"]
            scheme_id = scheme_slug_to_id.get(scheme_slug)
            if scheme_id is None:
                raise ValueError(
                    f"Class '{cls_data['identifier']}' references unknown "
                    f"concept scheme '{scheme_slug}'"
                )
            tax_id = scheme_slug_to_taxonomy_id[scheme_slug]

            parent_slug = cls_data.get("parent_class_identifier")
            parent_id: str | None = None
            if parent_slug:
                parent_id = class_slug_to_id.get(parent_slug)
                if parent_id is None:
                    raise ValueError(
                        f"Class '{cls_data['identifier']}' references unknown "
                        f"parent class '{parent_slug}'"
                    )

            ext_refs = external_refs_by_class_slug.get(cls_data["identifier"], [])
            external_refs_attached += len(ext_refs)

            domain_cls = Class(
                id=str(uuid.uuid4()),
                concept_scheme_id=scheme_id,
                taxonomy_id=tax_id,
                identifier=cls_data["identifier"],
                title=cls_data["title"],
                description=cls_data.get("description"),
                color=cls_data.get("color"),
                parent_class_id=parent_id,
                external_references=ext_refs,
                lexical_senses=self._coerce_lexical_senses(cls_data.get("lexical_senses")),
                status=Status.PUBLISHED,
                source_run_id=run_id,
            )
            saved_cls = self._repo.save_class(domain_cls)
            assert saved_cls.identifier is not None
            class_slug_to_id[saved_cls.identifier] = saved_cls.id

        return LoadResult(
            dataset_name=name,
            source_run_id=run_id,
            taxonomies=len(taxonomy_slug_to_id),
            concept_schemes=len(scheme_slug_to_id),
            classes=len(class_slug_to_id),
            property_definitions=property_defs_count,
            individuals=0,
            relationships=0,
            external_references=external_refs_attached,
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _coerce_status(value: Any) -> Status:
        """Coerce a string status from canon JSON to the Status enum."""
        if isinstance(value, str):
            try:
                return Status(value)
            except ValueError:
                return Status.PUBLISHED
        return Status.PUBLISHED

    @staticmethod
    def _coerce_lexical_senses(value: Any) -> list[LexicalSense]:
        """Coerce a list of lexical-sense dicts into LexicalSense value objects."""
        if not value:
            return []
        result: list[LexicalSense] = []
        for entry in value:
            if isinstance(entry, dict) and {"label", "language_code", "sense_type"} <= entry.keys():
                result.append(
                    LexicalSense(
                        label=entry["label"],
                        language_code=entry["language_code"],
                        sense_type=entry["sense_type"],
                    )
                )
        return result

    @staticmethod
    def _read_canon(dataset_dir: Path) -> dict[str, Any]:
        """Read and parse the canon.json master file for a dataset."""
        canon_path = dataset_dir / "canon.json"
        if not canon_path.is_file():
            raise FileNotFoundError(f"canon.json not found in {dataset_dir}")
        return json.loads(canon_path.read_text(encoding="utf-8"))

    @staticmethod
    def _read_papers(dataset_dir: Path) -> dict[str, dict[str, Any]]:
        """Read all paper_*.json fixtures and return them keyed by 'name'."""
        papers: dict[str, dict[str, Any]] = {}
        for path in sorted(dataset_dir.glob("paper_*.json")):
            try:
                paper = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed paper fixture %s: %s", path, exc)
                continue
            key = paper.get("name") or path.stem.replace("paper_", "")
            papers[key] = paper
        return papers

    @staticmethod
    def _collect_external_refs(
        papers: dict[str, dict[str, Any]],
    ) -> dict[str, list[ExternalReference]]:
        """
        Build a class-slug -> list[ExternalReference] map from all paper fixtures.

        Deduplicates by (source, identifier) so the same external reference
        mentioned in multiple papers is attached once.
        """
        accumulator: dict[str, dict[tuple[str, str], ExternalReference]] = defaultdict(dict)
        for paper in papers.values():
            for ref in paper.get("expected_external_refs", []):
                class_slug = ref.get("class_identifier") or ref.get("class_title")
                source = ref.get("source")
                identifier = ref.get("identifier")
                if not (class_slug and source and identifier):
                    continue
                key = (source, identifier)
                metadata = ref.get("metadata")
                external_ref = ExternalReference(
                    source=source,
                    identifier=identifier,
                    uri=ref.get("uri"),
                    metadata=(
                        MappingProxyType(dict(metadata)) if isinstance(metadata, dict) else None
                    ),
                )
                accumulator[class_slug][key] = external_ref
        return {slug: list(refs.values()) for slug, refs in accumulator.items()}

    @staticmethod
    def _topological_sort_classes(
        classes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Topologically sort canon classes so each class is preceded by its parent.

        Classes with no parent (parent_class_identifier is None) come first.
        Raises ValueError if a cycle is detected.
        """
        remaining = {c["identifier"]: c for c in classes}
        ordered: list[dict[str, Any]] = []
        placed: set[str] = set()

        # Iterate until everything is placed; bail on cycles.
        max_iterations = len(remaining) + 1
        while remaining and max_iterations > 0:
            progress = False
            for slug, cls in list(remaining.items()):
                parent = cls.get("parent_class_identifier")
                if parent is None or parent in placed:
                    ordered.append(cls)
                    placed.add(slug)
                    del remaining[slug]
                    progress = True
            if not progress:
                raise ValueError(
                    "Cycle or dangling parent reference detected in canon "
                    f"class_hierarchy among: {list(remaining.keys())}"
                )
            max_iterations -= 1

        return ordered

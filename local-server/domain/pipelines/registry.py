"""
Pipeline registries for type, implementation, and configuration discovery.

Three registries enable runtime enumeration and instantiation:
1. PipelineTypeRegistry — enumerates the pipeline types with input/output contracts
2. PipelineImplementationRegistry — maps (type, impl_id) → implementation class
3. PipelineConfigurationRegistry — maps (type, impl_id, config_ref) → configuration object
   (versioned; once referenced by a run, the version is immutable)

Defaults are declared here, at registration, and nowhere else: each pipeline
type has one default implementation and each implementation one default
configuration. Callers that name no implementation or configuration get these
through PipelineResolver (domain/pipelines/selection.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from domain.pipelines.entities import PipelineType


@dataclass(frozen=True)
class PipelineTypeDefinition:
    """
    Metadata for a pipeline type.

    Attributes:
        pipeline_type: The PipelineType enum value
        description: Human-readable description
        input_contract: Dict describing expected input schema
        output_contract: Dict describing expected output schema
    """

    pipeline_type: PipelineType
    description: str
    input_contract: dict[str, Any]
    output_contract: dict[str, Any]


class PipelineTypeRegistry:
    """
    Registry of all pipeline types.

    Enumerates the pipeline types with their input/output contracts.
    Discoverable at runtime by UX listing endpoints and script harness.
    """

    _TYPES = {
        PipelineType.NO_OP: PipelineTypeDefinition(
            pipeline_type=PipelineType.NO_OP,
            description="No-op pipeline for testing framework end-to-end",
            input_contract={
                "text": "str (required) — sample input text",
                "ontology_id": "str (required) — target ontology identifier",
            },
            output_contract={
                "status": "str — completion status",
                "message": "str — result message",
                "steps": "list[str] — completed steps",
            },
        ),
        PipelineType.INDIVIDUAL_EXTRACTION: PipelineTypeDefinition(
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            description="Extract RDF triples from individual text documents",
            input_contract={
                "text": "str (required) — source text to extract from",
                "ontology_id": "str (required) — target ontology identifier",
                "dataset_id": "str (optional) — dataset recognition matches individuals in",
                "source_id": (
                    "str (optional) — the source the text came from; carried into"
                    " metadata.source_id. Any of source_id, page_starts, headings or"
                    " pages extracts the text chunk by chunk (about 8000 characters,"
                    " split at headings, then pages, never mid-sentence); the chunks"
                    " are the run's items (items_done/items_total)"
                ),
                "page_starts": (
                    "list[int] (optional) — character offset at which each page starts,"
                    " in page order; numbers passage pages from 1"
                ),
                "headings": (
                    "list[{start: int, title: str, level: int}] (optional) — headings"
                    " in the text; chunks break at them first"
                ),
                "pages": (
                    'str (optional) — page selection such as "12-30" or "1-3, 7";'
                    " only text on those pages is extracted. Needs page_starts"
                ),
                "source_title": (
                    "str (optional) — the source's title, for the title of the proposal a"
                    " run on a source ends in"
                ),
                "extraction_id": (
                    "str (optional) — the extract call that started the run (runs started"
                    " together share it); recorded in input_summary with source_id"
                ),
                "skip_boilerplate": (
                    "bool (optional, true by default) — on a source, skip its warranty,"
                    " safety, legal and contact sections and its copies in other languages"
                    " (see domain/extraction/section_filter.py); false reads everything"
                ),
            },
            output_contract={
                "proposal_id": (
                    "str | null — a run on a source (source_id) ends in one change proposal"
                    " of its merged triples (individual and relationship creates with"
                    " evidence and near-match alternatives); null when nothing was proposed."
                    " With proposed_operations, refused_operations [{label, error}] and"
                    " skipped_candidates [{label, reason}]"
                ),
                "triples": (
                    "list[dict] — extracted triples with subject, predicate, object,"
                    " confidence and provenance {quote, start, end}. Chunked runs merge"
                    " a triple found in several chunks into one and add passages:"
                    " [{quote, start, end, page}] (provenance is the first placed passage;"
                    " offsets index the whole text). An individual's typing triple"
                    " carries near_matches: [{entity_id, label, similarity}] when"
                    " recognition found existing individuals close to it"
                ),
                "warnings": "list[str] — validation issues during extraction",
                "skipped_sections": (
                    "list[dict] — a run on a source: the sections it left unread,"
                    " [{start, end, page_first, page_last, reason, preview}] (reason:"
                    " other_language, warranty, safety, legal or contact), with"
                    " skipped_sections_by_reason {reason: count}; absent when none"
                ),
                "failed_chunks": (
                    "list[dict] — a run on a source: the chunks whose extraction failed"
                    " (for one, an LLM response that stayed incomplete), as in"
                    " metadata.chunks; what they hold, or part of it (each failure_reason says"
                    " which), is missing from triples and the"
                    " proposal, and that proposal supersedes no other proposal of the source."
                    " Absent when none; a run fails when every chunk failed whole"
                ),
                "metadata": (
                    "dict — model, tokens_used, duration_ms; chunked runs add source_id,"
                    " pages and chunks: [{index, start, end, page_first, page_last,"
                    " heading, triples, failure_reason}]"
                ),
            },
        ),
        PipelineType.SCHEMA_EXTRACTION: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            description="Extract schema structure from documents",
            input_contract={
                "documents": "list[str] — source documents to extract from",
                "scope": (
                    "str (optional) — the taxonomy extracted for (ontology_id also names it);"
                    " its classes are matched and offered as parents and attribute owners"
                ),
                "source_id": (
                    "str (optional) — the source the documents are; the run ends in one"
                    " change proposal of its candidates (class, attribute, predicate and"
                    " relationship-type creates with evidence) to the scope's taxonomy"
                ),
                "pages": (
                    'str (optional) — page selection such as "12-30"; only text on those'
                    " pages is read. Needs page_starts (offset at which each page starts)"
                ),
                "skip_boilerplate": (
                    "bool (optional, true by default) — on a source, skip its warranty,"
                    " safety, legal and contact sections and its copies in other languages"
                    " (see domain/extraction/section_filter.py); false reads everything"
                ),
            },
            output_contract={
                "candidates": (
                    "list[dict] — by kind: class {label, proposed_definition, proposed_parent"
                    " (title of an existing class or another class candidate it is a kind of,"
                    " or null), confidence, provenance, disambiguation_rationale};"
                    " property_definition {label, proposed_domain, proposed_range, ...};"
                    " attribute {label, proposed_definition, of (title of the existing class or"
                    " class candidate it describes, null when none resolves), value_type"
                    " (string | integer | number | date | boolean), unit, confidence,"
                    " provenance} — a measurement or other value placed on a class instead"
                    " of becoming one"
                ),
                "connections": "list[dict] — {subject_ref, predicate, object_ref, confidence}",
                "candidate_count": "int — class candidates",
                "property_count": "int — property candidates",
                "attribute_count": "int — attribute candidates",
                "proposal_id": (
                    "str | null — a run on a source: its proposal, null when nothing was"
                    " proposed (with proposed_operations, refused_operations, skipped_candidates)"
                ),
                "skipped_sections": (
                    "list[dict] — a run on a source: the sections it left unread, as for"
                    " individual_extraction, with skipped_sections_by_reason"
                ),
            },
        ),
        PipelineType.SCHEMA_NODE_GROUNDING: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            description="Ground schema nodes to external knowledge sources",
            input_contract={
                "nodes": "list[dict] — schema nodes to ground",
                "sources": "list[str] — external knowledge sources",
            },
            output_contract={
                "groundings": "list[dict] — grounding results with URIs and confidence",
            },
        ),
        PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            description=(
                "Refine schema node definitions using LLM: one node's candidates, or a"
                " taxonomy's operational definitions proposed (definition enrichment)"
            ),
            input_contract={
                "node_id": "str — the class or property definition to refine (one-node mode)",
                "current_definition": "str — current definition text (one-node mode)",
                "context": "str (optional) — additional context for refinement",
                "taxonomy_id": "str — the taxonomy to enrich (scoped mode, without node_id)",
                "scope": (
                    "str | list[str] | dict | None — a scheme id or identifier, class ids or"
                    " identifiers, {concept_scheme_id} or {class_ids}; None for every class"
                ),
            },
            output_contract={
                "candidates": "list[dict] — one-node mode: up to 3 candidate definitions",
                "proposal_id": "str | None — scoped mode: the change proposal made",
                "proposed": "int — scoped mode: classes with a proposed update",
            },
        ),
        PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            description="Refine connections between schema nodes",
            input_contract={
                "scope_id": "str (required) — UUID of the scope containing the connections",
                "current_connections": "list[dict] (optional) — current connections to refine",
                "strategy": "str (optional) — refinement strategy",
            },
            output_contract={
                "refined_connections": "list[dict] — refined connections with updated properties",
            },
        ),
        PipelineType.SCHEMA_RELATIONSHIP_REFLECTION: PipelineTypeDefinition(
            pipeline_type=PipelineType.SCHEMA_RELATIONSHIP_REFLECTION,
            description=(
                "Ask sorting questions (best source, target, predicate) per relationship"
                " type and propose the resulting change plan"
            ),
            input_contract={
                "taxonomy_id": "str (required) — taxonomy to reflect on",
                "scope": (
                    "str | list[str] | None — a scheme id or identifier, relationship type"
                    " ids, or None for the whole taxonomy"
                ),
            },
            output_contract={
                "proposal_id": "str | None — the change proposal made from the plan",
                "outcomes": "dict — reflections per outcome (reproduced, no_better, alternative)",
                "plan": "list[dict] — change plan rows (kind, replacement, p)",
                "reflections": "list[dict] — ranked answers per relationship type",
            },
        ),
        PipelineType.CLAIM_TRIAGE: PipelineTypeDefinition(
            pipeline_type=PipelineType.CLAIM_TRIAGE,
            description=(
                "Ask a decision model about each claim (validity, category, severity, fix"
                " scope, whether a pending definition addresses it) and save the answers"
            ),
            input_contract={
                "taxonomy_id": "str (required) — taxonomy whose claims to triage",
                "scope": (
                    "dict | None — {keys: [...]}, {note_ref}, {subject_ids: [...]},"
                    " {concept_scheme_id}, {untriaged: true}; None means untriaged claims"
                ),
            },
            output_contract={
                "claims": "int — claims triaged",
                "validity": "dict — triaged claims per validity",
                "errors": "list[str] — claims the decision model didn't answer",
            },
        ),
        PipelineType.NOTES_TO_CLAIMS: PipelineTypeDefinition(
            pipeline_type=PipelineType.NOTES_TO_CLAIMS,
            description=(
                "Split maintainer and reviewer notes into atomic claims, each naming the"
                " entities it affects, and store them as the taxonomy's claims"
            ),
            input_contract={
                "taxonomy_id": "str (required) — taxonomy the notes are about",
                "scope": (
                    "dict (required) — {notes: [{ref, subject, text, source?}]} (subject:"
                    " a Context Studio id or identifier, e.g. a class identifier or"
                    " '<class identifier>.<attribute identifier>'; a client maps its own"
                    " ids), {proposal_id} (its operations' notes and its decisions'"
                    " reasons), or {since: ISO datetime} (decision reasons in the"
                    " taxonomy's gold); plus force: true to re-split notes split already"
                ),
            },
            output_contract={
                "notes": "int — notes split",
                "skipped": (
                    "int — notes split already (claims from the same text, or a claim"
                    " with a verdict), left as they are without force"
                ),
                "claims": "int — claims stored (added or replaced by key)",
                "claims_removed": "int — earlier claims of those notes the new split dropped",
                "errors": "list[str] — notes that could not be split",
            },
        ),
    }

    @classmethod
    def get_type(cls, pipeline_type: PipelineType) -> PipelineTypeDefinition | None:
        """Get metadata for a pipeline type."""
        return cls._TYPES.get(pipeline_type)

    @classmethod
    def list_types(cls) -> list[PipelineTypeDefinition]:
        """List all registered pipeline types."""
        return list(cls._TYPES.values())

    @classmethod
    def is_valid_type(cls, pipeline_type: PipelineType) -> bool:
        """Check if a pipeline type is registered."""
        return pipeline_type in cls._TYPES


class PipelineImplementationRegistry:
    """
    Registry mapping (pipeline_type, implementation_id) → implementation class.

    Implementations register via decorator or explicit call at startup.
    Used by orchestrator to instantiate and execute pipelines.
    """

    def __init__(self) -> None:
        """Initialize the implementation registry."""
        self._implementations: dict[tuple[PipelineType, str], type[Any]] = {}
        # Each pipeline type's default implementation
        self._defaults: dict[PipelineType, str] = {}

    def register(
        self, pipeline_type: PipelineType, impl_id: str, default: bool = False
    ) -> Callable[[type[Any]], type[Any]]:
        """
        Decorator to register an implementation.

        Example:
            @registry.register(PipelineType.INDIVIDUAL_EXTRACTION, "default", default=True)
            class IndividualExtractionImpl:
                ...

        Args:
            pipeline_type: Type of pipeline
            impl_id: Implementation identifier
            default: It is the type's default implementation

        Returns:
            Decorator function
        """

        def decorator(cls: type[Any]) -> type[Any]:
            self.register_impl(pipeline_type, impl_id, cls, default=default)
            return cls

        return decorator

    def register_impl(
        self,
        pipeline_type: PipelineType,
        impl_id: str,
        impl_class: type[Any],
        default: bool = False,
    ) -> None:
        """
        Register an implementation class.

        Args:
            pipeline_type: Type of pipeline
            impl_id: Implementation identifier
            impl_class: Implementation class
            default: It is the type's default implementation: the one a run
                uses when none is named. A type has exactly one.

        Raises:
            ValueError: If already registered, or the type has another default
        """
        key = (pipeline_type, impl_id)
        if key in self._implementations:
            raise ValueError(f"Implementation already registered: {pipeline_type.value}:{impl_id}")
        if default and pipeline_type in self._defaults:
            raise ValueError(
                f"{pipeline_type.value} already has a default implementation:"
                f" {self._defaults[pipeline_type]}"
            )
        self._implementations[key] = impl_class
        if default:
            self._defaults[pipeline_type] = impl_id

    def default_implementation(self, pipeline_type: PipelineType) -> str | None:
        """The type's default implementation, or None when none is registered as it."""
        return self._defaults.get(pipeline_type)

    def get(self, pipeline_type: PipelineType, impl_id: str) -> type[Any] | None:
        """Get an implementation class."""
        return self._implementations.get((pipeline_type, impl_id))

    def list_by_type(self, pipeline_type: PipelineType) -> dict[str, type[Any]]:
        """List all implementations for a pipeline type."""
        return {
            impl_id: impl_class
            for (ptype, impl_id), impl_class in self._implementations.items()
            if ptype == pipeline_type
        }

    def list_all(self) -> dict[tuple[PipelineType, str], type[Any]]:
        """List all registered implementations."""
        return dict(self._implementations)


@dataclass(frozen=True)
class ConfigurationVersion:
    """
    Versioned configuration reference.

    Once a PipelineRun references a configuration, that version is immutable.

    Attributes:
        pipeline_type: Type of pipeline
        implementation_id: Implementation identifier
        config_ref: Configuration reference slug (e.g., 'extraction-default')
        version: Version number (auto-incremented on update)
        config: Configuration dict (immutable once set)
    """

    pipeline_type: PipelineType
    implementation_id: str
    config_ref: str
    version: int
    config: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate version is positive."""
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")


class PipelineConfigurationRegistry:
    """
    Registry mapping (pipeline_type, impl_id, config_ref) → versioned configuration.

    Configurations are immutable once set. Updates increment the version;
    old versions remain accessible. A PipelineRun references a specific
    version via configuration_ref + the version it used at creation time.

    In-Memory Design and Server Restart Safety:

    This registry is entirely in-memory and NOT persisted to the database. It is
    populated at server startup by calling register_*() functions for each pipeline
    type (e.g., register_individual_extraction, register_schema_extraction) from
    domain/pipelines/{type}/bootstrap.py modules.

    These registration functions read from deterministic default configuration modules
    in domain/pipelines/{type}/configurations/default.py. After a server restart, all
    configurations are re-registered in the same order with the same version numbers.

    Therefore, a PipelineRun referencing (slug="extraction-default", version=3)
    created before restart will successfully resolve after restart, because version 3
    is regenerated from code. This is correct and intentional.

    Immutability Mechanism:

    Immutability is enforced by the architecture, not by explicit checks:
    - Each call to register() with the same slug creates a NEW version
      (incrementing the version number)
    - The ConfigurationVersion is a frozen dataclass, so it cannot be mutated
    - You cannot retrieve an existing version and modify it; register() always
      returns a freshly created ConfigurationVersion with an incremented version number
    - mark_version_referenced() tracks which versions are used by runs, documenting
      the immutability contract for observability and testing

    This design prevents the mutation error case by construction.
    """

    def __init__(self) -> None:
        """Initialize the configuration registry."""
        # Map: (type, impl_id, config_ref) → list of versions (oldest first)
        self._configs: dict[tuple[PipelineType, str, str], list[ConfigurationVersion]] = {}
        # Set of (type, impl_id, config_ref, version) pairs that are referenced by runs
        # Used to document the immutability contract and enable testing of the
        # architectural constraint that version-referenced configs cannot change
        self._referenced_versions: set[tuple[PipelineType, str, str, int]] = set()
        # Each implementation's default configuration
        self._defaults: dict[tuple[PipelineType, str], str] = {}
        # Configurations no new run may start with (see retire)
        self._retired: set[tuple[PipelineType, str, str]] = set()

    def register(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config_ref: str,
        config: dict[str, Any],
        default: bool = False,
        version: int | None = None,
    ) -> ConfigurationVersion:
        """
        Register or update a configuration.

        If config_ref exists, increments version and stores as new version.
        Otherwise, creates version 1. A configuration registered as its
        implementation's default stays the default through later versions.

        A stored (user-created) configuration is registered under the version
        its record holds, so the version a run was pinned to names the same
        content before and after a restart: at startup the record's latest
        content is registered as its stored version, and earlier versions,
        whose content is not kept, are not registered at all.

        Configuration versions are immutable by design: ConfigurationVersion is a frozen
        dataclass and versions are stored in an append-only list. Existing versions cannot
        be mutated; only new versions can be registered.

        Args:
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            config_ref: Configuration reference (slug)
            config: Configuration dict
            default: It is the implementation's default configuration: the one
                a run uses when none is named. An implementation has exactly one.
            version: The version to register it as (a stored configuration's
                own); the next one when omitted

        Returns:
            ConfigurationVersion just registered

        Raises:
            ValueError: If the implementation has another default
                configuration, or `version` is not above the latest registered
        """
        key = (pipeline_type, implementation_id, config_ref)
        versions = self._configs.get(key, [])
        if default:
            current = self._defaults.setdefault((pipeline_type, implementation_id), config_ref)
            if current != config_ref:
                raise ValueError(
                    f"{pipeline_type.value}:{implementation_id} already has a default"
                    f" configuration: {current}"
                )

        # Create a new version (incrementing the version number).
        # Since ConfigurationVersion is a frozen dataclass and stored in an append-only
        # list, existing versions cannot be mutated. Only new versions can be registered.

        next_version = (versions[-1].version + 1) if versions else 1
        if version is not None:
            if versions and version <= versions[-1].version:
                raise ValueError(
                    f"{pipeline_type.value}:{implementation_id}:{config_ref} is already"
                    f" registered at version {versions[-1].version}, not below {version}"
                )
            next_version = version

        version_obj = ConfigurationVersion(
            pipeline_type=pipeline_type,
            implementation_id=implementation_id,
            config_ref=config_ref,
            version=next_version,
            config=dict(config),  # Defensive copy
        )

        self._configs[key] = versions + [version_obj]
        return version_obj

    def retire(self, pipeline_type: PipelineType, implementation_id: str, config_ref: str) -> bool:
        """
        Retire a configuration (a deleted user configuration): no new run can
        be started with it and it is no longer listed (get_latest and
        list_configs leave it out). Its versions stay for the runs already
        pinned to them (get_version), until the process ends.

        Returns:
            True if it was registered

        Raises:
            ValueError: If it is its implementation's default configuration
        """
        if self._defaults.get((pipeline_type, implementation_id)) == config_ref:
            raise ValueError(
                f"{config_ref} is the default configuration of"
                f" {pipeline_type.value}:{implementation_id} and cannot be retired"
            )
        key = (pipeline_type, implementation_id, config_ref)
        if key not in self._configs:
            return False
        self._retired.add(key)
        return True

    def default_configuration(
        self, pipeline_type: PipelineType, implementation_id: str
    ) -> str | None:
        """The implementation's default configuration, or None when none is registered as it."""
        return self._defaults.get((pipeline_type, implementation_id))

    def get_latest(
        self, pipeline_type: PipelineType, implementation_id: str, config_ref: str
    ) -> ConfigurationVersion | None:
        """Get the latest version of a configuration; None for one that is retired."""
        key = (pipeline_type, implementation_id, config_ref)
        versions = self._configs.get(key, [])
        return versions[-1] if versions and key not in self._retired else None

    def get_version(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config_ref: str,
        version: int,
    ) -> ConfigurationVersion | None:
        """Get a specific version of a configuration."""
        key = (pipeline_type, implementation_id, config_ref)
        versions = self._configs.get(key, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_configs(
        self, pipeline_type: PipelineType, implementation_id: str
    ) -> list[tuple[str, ConfigurationVersion]]:
        """List (config_ref, latest_version) pairs for a type/impl combo, retired ones left out."""
        result = []
        for key, versions in self._configs.items():
            ptype, impl_id, config_ref = key
            if (
                ptype == pipeline_type
                and impl_id == implementation_id
                and versions
                and key not in self._retired
            ):
                result.append((config_ref, versions[-1]))
        return result

    def list_all_versions(
        self, pipeline_type: PipelineType, implementation_id: str, config_ref: str
    ) -> list[ConfigurationVersion]:
        """List all versions of a configuration."""
        key = (pipeline_type, implementation_id, config_ref)
        return self._configs.get(key, [])

    def mark_version_referenced(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config_ref: str,
        version: int,
    ) -> None:
        """
        Mark a configuration version as referenced by a PipelineRun.

        This documents the immutability contract: once a version is referenced by a run,
        that version will not be modified. New runs can only reference the latest version
        or explicitly pin an older version. Immutability is enforced by the architecture
        (ConfigurationVersion is a frozen dataclass stored in an append-only list).

        Args:
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            config_ref: Configuration reference (slug)
            version: Version number
        """
        key = (pipeline_type, implementation_id, config_ref, version)
        self._referenced_versions.add(key)

    def is_version_referenced(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config_ref: str,
        version: int,
    ) -> bool:
        """
        Check if a configuration version is referenced by a PipelineRun.

        Args:
            pipeline_type: Type of pipeline
            implementation_id: Implementation identifier
            config_ref: Configuration reference (slug)
            version: Version number

        Returns:
            True if this version is already referenced by a run
        """
        key = (pipeline_type, implementation_id, config_ref, version)
        return key in self._referenced_versions

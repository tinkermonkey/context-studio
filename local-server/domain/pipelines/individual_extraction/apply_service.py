"""
Apply service for individual extraction pipeline.

Converts RDF triple output from a completed individual extraction run into DRAFT
Individual entities via OntologyService (so they get validation, events, and
vector-index sync) and Relationship entities persisted via the OntologyRepository
port.

This is the shared materialization funnel for every individual-extraction
orchestrator (``default`` and ``open_v1``): both emit the same
``{triples, warnings, metadata}`` contract, so a recognition stage placed here
— rather than inside either orchestrator — runs uniformly regardless of which
one produced the triples. Recognition sits between extraction and
materialization: for each individual not already resolved locally, it attempts
to resolve the mention to an existing graph node via IndividualRecognizer
before minting a new one.

Idempotent: applying the same run twice produces no duplicates. Deduplication is
content-based (title within the first class_id for individuals; source+target+property
for relationships).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from domain.ontology.entities import Relationship
from domain.ontology.exceptions import DuplicateEntityError
from domain.pipelines.apply_result import ApplyResult

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.extraction.ports import IndividualRecognizer, RecognitionMatch
    from domain.ontology.entities import Class
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
    from domain.pipelines.entities import PipelineRun


class IndividualExtractionApplyService:
    """
    Materializes individual extraction pipeline output into ontology entities.

    Creates Individual entities via OntologyService.create_individual (DRAFT
    status, indexed for search) and Relationship entities directly via the
    repository, both tagged with source_run_id from the originating pipeline run.

    An optional IndividualRecognizer runs the recognition stage: for each
    individual not already resolved by the in-pass cache, an explicit ID, or an
    exact label match, the recognizer is offered the mention before it is
    treated as new. A match adopts the existing node's ID (and its canonical
    title stays authoritative — nothing is renamed); no match falls through to
    minting a new individual exactly as before. Passing no recognizer
    (the default) is a no-op placeholder seam: apply behaves exactly as it did
    before recognition existed.
    """

    def __init__(
        self,
        ontology_service: "OntologyService",
        ontology_repo: "OntologyRepository",
        individual_recognizer: "IndividualRecognizer | None" = None,
    ) -> None:
        self._ontology_service = ontology_service
        self._repo = ontology_repo
        self._recognizer = individual_recognizer

    def apply(
        self,
        run: "PipelineRun",
        confidence_threshold: float = 0.0,
        recognition_threshold: float | None = None,
    ) -> ApplyResult:
        """
        Apply individual extraction results to the ontology.

        Args:
            run: Completed PipelineRun with output_summary containing triples
            confidence_threshold: Minimum confidence to include a triple (0.0–1.0)
            recognition_threshold: Minimum similarity (0.0-1.0) the recognizer
                requires to resolve a mention to an existing individual.
                Defaults to the recognizer's own configured value when omitted.

        Returns:
            ApplyResult with counts of created and skipped entities
        """
        result = ApplyResult()
        triples = run.output_summary.get("triples", [])

        _logger.info(
            "individual extraction apply run=%s: recognition stage %s",
            run.id,
            "active" if self._recognizer is not None else "no-op (no recognizer configured)",
        )

        # Track individuals created in this apply pass: (title_lower, class_id) → entity_id.
        # Classless (open_v1) individuals use a label-only sentinel key ("" for class_id)
        # since they have no class_ids to key on.
        individual_key_to_id: dict[tuple[str, str], str] = {}

        # Individuals minted in this apply pass, so recognizer matches pointing back at
        # them can be rejected — recognition must only resolve against individuals that
        # already existed in the graph before this run, never against sibling mentions
        # extracted in the same pass.
        created_this_run: set[str] = set()

        for triple in triples:
            subject = triple.get("subject", {})
            predicate = triple.get("predicate", {})
            obj = triple.get("object", {})
            confidence = triple.get("confidence", 0.0)

            if confidence < confidence_threshold:
                result.individuals_skipped += 1
                continue

            if subject.get("kind") != "individual":
                continue

            subject_label = (subject.get("label") or "").strip()
            subject_id = subject.get("id", "")

            # Resolve class IDs for this individual from the triple object or subject context
            class_ids: list[str] = subject.get("class_ids") or []

            # Attempt to resolve subject individual: prefer explicit ID, then label+class lookup
            resolved_id = self._resolve_individual_id(
                subject_id, subject_label, class_ids, individual_key_to_id
            )

            if resolved_id is None:
                if not subject_label:
                    result.individuals_skipped += 1
                    continue

                # Verify all class_ids exist; class_ids may legitimately be empty
                # (e.g. an untyped open_v1 relation triple) — that only rules out
                # minting a new individual below, not attempting recognition.
                valid_classes: list["Class"] = [
                    cls for cid in class_ids if (cls := self._repo.get_class(cid)) is not None
                ]
                if class_ids and not valid_classes:
                    result.individuals_skipped += 1
                    continue
                valid_class_ids = [cls.id for cls in valid_classes]
                taxonomy_id = valid_classes[0].taxonomy_id if valid_classes else None

                # Recognition stage: resolve the mention to an existing graph node
                # before treating it as new. Runs for every orchestrator's output —
                # this apply() is the single funnel both share.
                match = self._recognize_individual(
                    subject_label, valid_class_ids, taxonomy_id, triple, recognition_threshold
                )

                if match is not None and match.individual_id in created_this_run:
                    _logger.info(
                        "recognition stage: '%s' -> match %s was created earlier in "
                        "this apply pass; ignoring same-run match",
                        subject_label,
                        match.individual_id,
                    )
                    match = None

                if match is not None:
                    resolved_id = match.individual_id
                    result.individuals_recognized += 1
                    result.recognized_individual_ids.append(resolved_id)
                elif not valid_class_ids:
                    # No recognizable match and nothing to type it as — nothing to do.
                    result.individuals_skipped += 1
                    continue
                else:
                    try:
                        new_individual = self._ontology_service.create_individual(
                            class_ids=valid_class_ids,
                            title=subject_label,
                            source_run_id=run.id,
                        )
                        resolved_id = new_individual.id
                        result.individuals_created += 1
                        result.created_individual_ids.append(resolved_id)
                        created_this_run.add(resolved_id)
                    except DuplicateEntityError:
                        # Another triple in this run (or a prior apply) already created
                        # this individual — resolve to its existing ID rather than
                        # failing the triple.
                        try:
                            resolved_id = self._find_individual_by_label(
                                subject_label, valid_class_ids
                            )
                        except Exception:
                            _logger.error(
                                "Failed to look up existing individual '%s' in classes "
                                "%s after DuplicateEntityError",
                                subject_label,
                                valid_class_ids,
                                exc_info=True,
                            )
                            raise
                        if resolved_id is None:
                            _logger.error(
                                "DuplicateEntityError creating individual '%s' but no "
                                "matching individual found in classes %s",
                                subject_label,
                                valid_class_ids,
                            )
                            raise
                        result.individuals_recognized += 1
                        result.recognized_individual_ids.append(resolved_id)
                    except Exception as e:
                        _logger.error(f"Failed to save individual: {e}")
                        raise

                # Cache for dedup within this apply pass. Classless individuals (no
                # valid_class_ids, e.g. open_v1 relation triples) have nothing to key
                # per-class, so fall back to a label-only sentinel key.
                if valid_class_ids:
                    for cid in valid_class_ids:
                        key = (subject_label.lower(), cid)
                        individual_key_to_id[key] = resolved_id
                    # Also store label-only entry for lookup by label alone
                    individual_key_to_id[(subject_label.lower(), "")] = resolved_id
                else:
                    individual_key_to_id[(subject_label.lower(), "")] = resolved_id

            # Create relationship if predicate + object are present
            property_definition_id = predicate.get("property_definition_id", "")
            obj_kind = obj.get("kind", "")
            obj_id = obj.get("id", "")

            # If object ID is not set but object is an individual with class_ids,
            # try to look it up in the created individuals cache
            if not obj_id and obj_kind == "individual":
                obj_label = (obj.get("label") or "").strip()
                obj_class_ids = obj.get("class_ids") or []
                if obj_label and obj_class_ids:
                    for cid in obj_class_ids:
                        key = (obj_label.lower(), cid)
                        if key in individual_key_to_id:
                            obj_id = individual_key_to_id[key]
                            break
                elif obj_label:
                    key = (obj_label.lower(), "")
                    if key in individual_key_to_id:
                        obj_id = individual_key_to_id[key]

            if property_definition_id and obj_kind in ("individual", "class") and obj_id:
                self._apply_relationship(
                    source_id=resolved_id,
                    target_id=obj_id,
                    property_definition_id=property_definition_id,
                    source_run_id=run.id,
                    result=result,
                )

        result.validate()
        return result

    def _find_individual_by_label(self, subject_label: str, class_ids: list[str]) -> str | None:
        """Return the ID of an existing individual with this title within any of the classes."""
        for cid in class_ids:
            candidates = self._repo.list_individuals(class_id=cid, limit=None)
            for ind in candidates:
                if ind.title.lower() == subject_label.lower():
                    return ind.id
        return None

    def _recognize_individual(
        self,
        label: str,
        class_ids: list[str],
        taxonomy_id: str | None,
        triple: dict,
        threshold: float | None = None,
    ) -> "RecognitionMatch | None":
        """
        Recognition stage: resolve an extracted mention to an existing graph node.

        A no-op (returns None immediately) when no recognizer is configured, so
        apply's output is unchanged from pre-recognition behavior. Otherwise
        delegates to IndividualRecognizer, scoped to ``class_ids`` (may be empty,
        which searches unscoped rather than skipping recognition outright — an
        untyped mention can still resolve to an existing typed individual).
        A recognizer failure is logged and treated as no-match, biasing the
        pipeline toward minting a new individual rather than failing the apply.
        Programming bugs (TypeError, AttributeError, KeyError, IndexError) are
        not treated as best-effort failures — they propagate so the underlying
        defect is surfaced instead of silently minting a duplicate individual.
        """
        if self._recognizer is None:
            return None

        try:
            match = self._recognizer.recognize(
                label=label,
                context=self._triple_context(triple),
                class_ids=class_ids,
                taxonomy_id=taxonomy_id,
                threshold=threshold,
            )
        except (TypeError, AttributeError, KeyError, IndexError):
            raise
        except Exception as exc:  # noqa: BLE001 - recognition is best-effort
            _logger.error("Recognition stage failed for '%s': %s", label, exc, exc_info=True)
            return None

        if match is not None:
            _logger.info(
                "recognition stage: '%s' -> matched individual %s ('%s', method=%s, score=%.3f)",
                label,
                match.individual_id,
                match.title,
                match.method,
                match.score,
            )
        else:
            _logger.info("recognition stage: '%s' -> no match; will mint a new individual", label)
        return match

    @staticmethod
    def _triple_context(triple: dict) -> str:
        """Best-effort surrounding text for the recognizer's LLM tiebreak tier."""
        provenance = triple.get("provenance") or {}
        raw = provenance.get("raw")
        if raw:
            return str(raw)
        subject_label = triple.get("subject", {}).get("label", "")
        predicate_label = triple.get("predicate", {}).get("label", "")
        object_label = triple.get("object", {}).get("label", "")
        if predicate_label and object_label:
            return f"{subject_label} {predicate_label} {object_label}".strip()
        return str(subject_label)

    def _resolve_individual_id(
        self,
        subject_id: str,
        subject_label: str,
        class_ids: list[str],
        local_cache: dict[tuple[str, str], str],
    ) -> str | None:
        """Return existing individual ID if found, else None."""
        # Check local cache first (individuals created earlier in this apply pass).
        # Classless mentions (e.g. open_v1 relation triples with no class_ids) were
        # cached under a label-only sentinel key, since there's no class to key on.
        if class_ids:
            for cid in class_ids:
                cached = local_cache.get((subject_label.lower(), cid))
                if cached:
                    return cached
        else:
            cached = local_cache.get((subject_label.lower(), ""))
            if cached:
                return cached

        # Try lookup by explicit ID
        if subject_id:
            existing = self._repo.get_individual(subject_id)
            if existing:
                return existing.id

        # Try lookup by label within each class
        return self._find_individual_by_label(subject_label, class_ids)

    def _apply_relationship(
        self,
        source_id: str,
        target_id: str,
        property_definition_id: str,
        source_run_id: str,
        result: ApplyResult,
    ) -> None:
        """Create a relationship if it does not already exist."""
        if source_id == target_id:
            result.relationships_skipped += 1
            return

        existing = self._repo.list_relationships(
            source_id=source_id,
            target_id=target_id,
            property_id=property_definition_id,
            limit=1,
        )
        if existing:
            result.relationships_skipped += 1
            return

        try:
            new_rel = Relationship(
                id=str(uuid4()),
                source_id=source_id,
                target_id=target_id,
                property_definition_id=property_definition_id,
                source_run_id=source_run_id,
            )
            self._repo.save_relationship(new_rel)
            result.relationships_created += 1
            result.created_relationship_ids.append(new_rel.id)
        except Exception as e:
            _logger.error(f"Failed to save relationship: {e}")
            raise

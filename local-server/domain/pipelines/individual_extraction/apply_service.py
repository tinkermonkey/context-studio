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
from domain.pipelines.apply_result import ApplyResult, MergedMention
from domain.pipelines.apply_selection import (
    MERGE,
    SEPARATE,
    RecognitionDecision,
    check_accepted_ids,
)
from domain.pipelines.candidate_ids import enumerate_triples, mention_key
from domain.pipelines.exceptions import ApplySelectionError

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
        accepted_candidate_ids: "set[str] | list[str] | None" = None,
        recognition_decisions: "list[RecognitionDecision] | None" = None,
    ) -> ApplyResult:
        """
        Apply individual extraction results to the ontology.

        Args:
            run: Completed PipelineRun with output_summary containing triples
            confidence_threshold: Minimum confidence to include a triple (0.0–1.0).
                Ignored when ``accepted_candidate_ids`` is given.
            recognition_threshold: Minimum similarity (0.0-1.0) the recognizer
                requires to resolve a mention to an existing individual.
                Defaults to the recognizer's own configured value when omitted.
            accepted_candidate_ids: Explicit reviewer selection of triple ids
                (``triple-{i}``); when given it is the full selection — every
                other triple is skipped regardless of confidence.
            recognition_decisions: Per-mention reviewer decisions. ``merge``
                adopts the given pre-existing individual without consulting the
                recognizer; ``separate`` skips the recognizer so the mention is
                minted new (an existing same-title individual in the class still
                wins, since titles are unique per class). Mentions without a
                decision go through recognition as usual.

        Returns:
            ApplyResult with counts of created and skipped entities

        Raises:
            ApplySelectionError: If an accepted id or decision does not match the
                run, or a merge target does not exist. Raised before any write.
        """
        result = ApplyResult()
        enumerated = enumerate_triples(run.output_summary)
        check_accepted_ids(accepted_candidate_ids, {cid for cid, _ in enumerated})
        decisions = self._index_decisions([t for _, t in enumerated], recognition_decisions or [])
        selected = set(accepted_candidate_ids) if accepted_candidate_ids is not None else None
        # Mentions already reported in merged_mentions, so each appears once.
        reported_mentions: set[str] = set()

        _logger.info(
            "individual extraction apply run=%s: recognition stage %s",
            run.id,
            ("active" if self._recognizer is not None else "no-op (no recognizer configured)"),
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

        for candidate_id, triple in enumerated:
            subject = triple.get("subject", {})
            predicate = triple.get("predicate", {})
            obj = triple.get("object", {})
            confidence = triple.get("confidence", 0.0)

            if selected is not None:
                if candidate_id not in selected:
                    result.individuals_skipped += 1
                    result.skipped_candidate_ids.append(candidate_id)
                    continue
            elif confidence < confidence_threshold:
                result.individuals_skipped += 1
                result.skipped_candidate_ids.append(candidate_id)
                continue

            if subject.get("kind") != "individual":
                result.skipped_candidate_ids.append(candidate_id)
                continue

            subject_label = (subject.get("label") or "").strip()
            subject_id = subject.get("id", "")
            subject_key = mention_key(subject_label)
            decision = decisions.get(subject_key)

            # Resolve class IDs for this individual from the triple object or subject context
            class_ids: list[str] = subject.get("class_ids") or []

            # Resolve the subject: in-pass cache first, then a reviewer merge
            # decision, then an explicit ID, then an exact label+class lookup.
            resolved_id = self._cached_individual_id(subject_label, class_ids, individual_key_to_id)
            if resolved_id is None and decision is not None and decision.decision == MERGE:
                resolved_id = decision.individual_id
                result.individuals_recognized += 1
                result.recognized_individual_ids.append(resolved_id)
                self._report_merge(
                    result, reported_mentions, subject_label, resolved_id, "decision"
                )
                self._cache_individual(individual_key_to_id, subject_label, class_ids, resolved_id)
            if resolved_id is None and subject_id:
                existing = self._repo.get_individual(subject_id)
                if existing:
                    resolved_id = existing.id
            if resolved_id is None:
                resolved_id = self._find_individual_by_label(subject_label, class_ids)
                if resolved_id is not None:
                    self._report_merge(
                        result, reported_mentions, subject_label, resolved_id, "existing_title"
                    )

            if resolved_id is None:
                if not subject_label:
                    result.individuals_skipped += 1
                    result.skipped_candidate_ids.append(candidate_id)
                    continue

                # Verify all class_ids exist; class_ids may legitimately be empty
                # (e.g. an untyped open_v1 relation triple) — that only rules out
                # minting a new individual below, not attempting recognition.
                valid_classes: list["Class"] = [
                    cls for cid in class_ids if (cls := self._repo.get_class(cid)) is not None
                ]
                if class_ids and not valid_classes:
                    result.individuals_skipped += 1
                    result.skipped_candidate_ids.append(candidate_id)
                    continue
                valid_class_ids = [cls.id for cls in valid_classes]
                taxonomy_id = valid_classes[0].taxonomy_id if valid_classes else None

                # Recognition stage: resolve the mention to an existing graph node
                # before treating it as new. Runs for every orchestrator's output —
                # this apply() is the single funnel both share. A reviewer's
                # "separate" decision skips it.
                match = None
                if decision is None or decision.decision != SEPARATE:
                    match = self._recognize_individual(
                        subject_label,
                        valid_class_ids,
                        taxonomy_id,
                        triple,
                        recognition_threshold,
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
                    self._report_merge(
                        result, reported_mentions, subject_label, resolved_id, "recognition"
                    )
                elif not valid_class_ids:
                    # No recognizable match and nothing to type it as — nothing to do.
                    result.individuals_skipped += 1
                    result.skipped_candidate_ids.append(candidate_id)
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
                        self._report_merge(
                            result, reported_mentions, subject_label, resolved_id, "existing_title"
                        )
                    except Exception as e:
                        _logger.error(f"Failed to save individual: {e}")
                        raise

                # Cache for dedup within this apply pass.
                self._cache_individual(
                    individual_key_to_id, subject_label, valid_class_ids, resolved_id
                )

            result.applied_candidate_ids.append(candidate_id)

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
                    # Fall back to label-only entry if no class_id matched
                    if not obj_id:
                        key = (obj_label.lower(), "")
                        if key in individual_key_to_id:
                            obj_id = individual_key_to_id[key]
                elif obj_label:
                    key = (obj_label.lower(), "")
                    if key in individual_key_to_id:
                        obj_id = individual_key_to_id[key]

                if not obj_id and obj_label:
                    _logger.warning(
                        "Object lookup for %r with classes %s not found in cache; skipping",
                        obj_label,
                        obj_class_ids,
                    )

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
        quote = provenance.get("quote") or provenance.get("raw")
        if quote:
            return str(quote)
        subject_label = triple.get("subject", {}).get("label", "")
        predicate_label = triple.get("predicate", {}).get("label", "")
        object_label = triple.get("object", {}).get("label", "")
        if predicate_label and object_label:
            return f"{subject_label} {predicate_label} {object_label}".strip()
        return str(subject_label)

    def _index_decisions(
        self, triples: list[dict], decisions: list["RecognitionDecision"]
    ) -> dict[str, "RecognitionDecision"]:
        """
        Validate reviewer recognition decisions and index them by mention key.

        A decision must name a subject individual mention the run extracted (the
        same mentions recognition preview reports), at most once, and a merge must
        target an individual that already exists. All problems are collected into
        a single ApplySelectionError so nothing is written for a bad request.
        """
        if not decisions:
            return {}
        known = {
            mention_key(t.get("subject", {}).get("label"))
            for t in triples
            if t.get("subject", {}).get("kind") == "individual"
        }
        known.discard("")
        indexed: dict[str, "RecognitionDecision"] = {}
        problems: list[str] = []
        for d in decisions:
            key = mention_key(d.mention_label)
            if key not in known:
                problems.append(f"no extracted mention '{d.mention_label}'")
                continue
            if key in indexed:
                problems.append(f"more than one decision for mention '{d.mention_label}'")
                continue
            if d.decision == MERGE:
                if not d.individual_id:
                    problems.append(f"merge for '{d.mention_label}' has no individual_id")
                    continue
                if self._repo.get_individual(d.individual_id) is None:
                    problems.append(
                        f"merge target individual '{d.individual_id}' for "
                        f"'{d.mention_label}' does not exist"
                    )
                    continue
            elif d.decision != SEPARATE:
                problems.append(f"unknown decision '{d.decision}' for '{d.mention_label}'")
                continue
            indexed[key] = d
        if problems:
            raise ApplySelectionError("Invalid recognition decisions: " + "; ".join(problems))
        return indexed

    @staticmethod
    def _cached_individual_id(
        subject_label: str,
        class_ids: list[str],
        local_cache: dict[tuple[str, str], str],
    ) -> str | None:
        """Return an individual resolved earlier in this apply pass, else None."""
        # Classless mentions (e.g. open_v1 relation triples with no class_ids) were
        # cached under a label-only sentinel key, since there's no class to key on.
        if class_ids:
            for cid in class_ids:
                cached = local_cache.get((subject_label.lower(), cid))
                if cached:
                    return cached
            return None
        return local_cache.get((subject_label.lower(), ""))

    @staticmethod
    def _cache_individual(
        local_cache: dict[tuple[str, str], str],
        subject_label: str,
        class_ids: list[str],
        individual_id: str,
    ) -> None:
        """Remember a resolved mention per class plus a label-only entry for objects."""
        for cid in class_ids:
            local_cache[(subject_label.lower(), cid)] = individual_id
        local_cache[(subject_label.lower(), "")] = individual_id

    @staticmethod
    def _report_merge(
        result: ApplyResult,
        reported: set[str],
        mention_label: str,
        individual_id: str,
        source: str,
    ) -> None:
        """Record a mention merged into a pre-existing individual, once per mention."""
        key = mention_key(mention_label)
        if key in reported:
            return
        reported.add(key)
        result.merged_mentions.append(
            MergedMention(mention_label=mention_label, individual_id=individual_id, source=source)
        )

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

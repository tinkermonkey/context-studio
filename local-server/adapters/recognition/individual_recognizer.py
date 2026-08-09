"""
Adapter for the IndividualRecognizer port.

Implements the three-tier match cascade — exact label match, a single clear
vector-similarity winner, or an LLM tiebreak when candidates fall within a
small score band of each other — against the IndividualVectorIndex port.
Matching is scoped to the caller's class_ids only; cross-class matching is
deferred to a future adapter.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Sequence

from domain.extraction.ports import RecognitionMatch
from domain.ontology.ports import EmbeddingService, IndividualMatch, IndividualVectorIndex
from domain.pipelines.ports import LLMProvider

_logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "google/gemini-3-flash-preview"

_TIEBREAK_SYSTEM_PROMPT = (
    "You are an entity-resolution assistant. Given a mention extracted from "
    "text, its surrounding context, and a list of existing individuals that "
    "are all plausible matches, decide which single individual - if any - "
    "refers to the same real-world entity as the mention. Do not invent an "
    'id. Respond with only JSON: {"individual_id": "<id or none>"}.'
)


class CascadeIndividualRecognizer:
    """
    IndividualRecognizer adapter: exact match -> clear vector winner -> LLM tiebreak.

    Composes an IndividualVectorIndex (candidate retrieval) and an
    EmbeddingService (query embedding) with an optional LLMProvider. Without
    an LLM provider, an ambiguous case (multiple candidates within
    ``tiebreak_band`` of the top score) degrades to the highest-scoring
    candidate rather than failing, so the recognizer stays functional without
    LLM cost.
    """

    def __init__(
        self,
        individual_index: IndividualVectorIndex,
        embedding_service: EmbeddingService,
        llm: LLMProvider | None = None,
        threshold: float = 0.90,
        tiebreak_band: float = 0.05,
        top_k: int = 5,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        """
        Args:
            individual_index: Vector index over existing graph individuals.
            embedding_service: Embeds the mention label for vector search.
            llm: Optional LLM provider used only for the tier-3 tiebreak.
                When None, an ambiguous case falls back to the top-scoring
                candidate instead of failing.
            threshold: Default minimum similarity (0.0-1.0) a candidate must
                clear to be considered, unless overridden per call. Kept
                independent of the class-grounding similarity_threshold used
                elsewhere in extraction.
            tiebreak_band: Candidates within this many similarity points of
                the top score are treated as tied and routed to the tiebreak
                tier.
            top_k: Maximum candidates retrieved from the index per call.
            model: LLM model identifier used for tiebreak calls.

        Raises:
            ValueError: If threshold or tiebreak_band is not 0.0-1.0.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be 0.0-1.0, got {threshold}")
        if not 0.0 <= tiebreak_band <= 1.0:
            raise ValueError(f"tiebreak_band must be 0.0-1.0, got {tiebreak_band}")
        self._individual_index = individual_index
        self._embedding_service = embedding_service
        self._llm = llm
        self._threshold = threshold
        self._tiebreak_band = tiebreak_band
        self._top_k = top_k
        self._model = model

    def recognize(
        self,
        label: str,
        context: str,
        class_ids: Sequence[str],
        taxonomy_id: str | None = None,
        threshold: float | None = None,
    ) -> RecognitionMatch | None:
        """Resolve a mention to an existing individual via the match cascade."""
        mention = label.strip()
        if not mention:
            return None

        effective_threshold = self._threshold if threshold is None else threshold
        embedding = self._embedding_service.embed(mention)
        candidates = self._individual_index.search(
            embedding, class_ids=list(class_ids), top_k=self._top_k, threshold=0.0
        )
        if not candidates:
            return None

        exact = self._exact_match(mention, candidates)
        if exact is not None:
            return RecognitionMatch(exact.individual_id, exact.title, 1.0, "exact")

        qualifying = [c for c in candidates if c.score >= effective_threshold]
        if not qualifying:
            return None

        tied = self._tied_candidates(qualifying)
        top = tied[0]
        if len(tied) == 1:
            return RecognitionMatch(top.individual_id, top.title, top.score, "vector")

        llm = self._llm
        if llm is None:
            return RecognitionMatch(top.individual_id, top.title, top.score, "vector")

        chosen, confirmed = self._llm_tiebreak(llm, mention, context, tied)
        if chosen is None:
            return None
        method = "llm" if confirmed else "vector"
        return RecognitionMatch(chosen.individual_id, chosen.title, chosen.score, method)

    @staticmethod
    def _exact_match(mention: str, candidates: list[IndividualMatch]) -> IndividualMatch | None:
        """Case-insensitive exact title match, checked ahead of any score."""
        mention_lower = mention.lower()
        for candidate in candidates:
            if candidate.title.strip().lower() == mention_lower:
                return candidate
        return None

    def _tied_candidates(self, qualifying: list[IndividualMatch]) -> list[IndividualMatch]:
        """Candidates within tiebreak_band of the top score, highest first."""
        top_score = qualifying[0].score
        return [c for c in qualifying if (top_score - c.score) < self._tiebreak_band]

    def _llm_tiebreak(
        self, llm: LLMProvider, mention: str, context: str, tied: list[IndividualMatch]
    ) -> tuple[IndividualMatch | None, bool]:
        """
        Ask the LLM to pick among near-equal candidates, or confirm none match.

        Returns (match, confirmed). confirmed is True only when the LLM
        actually named a candidate (or explicitly said none match) — the
        caller uses it to decide whether the match's provenance is "llm" or
        a score-based fallback. Falls back to the top-scoring tied candidate,
        unconfirmed, when the LLM call fails or the response can't be parsed
        or names an id outside the tied set, so any of those degrade to a
        best guess rather than raising or silently mislabeling provenance.
        """
        lines = [self._describe_candidate(c) for c in tied]
        user_prompt = (
            f'Mention: "{mention}"\n'
            f'Context: "{context}"\n\n'
            "Candidate existing individuals:\n" + "\n".join(lines)
        )
        try:
            response = llm.complete(
                system_prompt=_TIEBREAK_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=self._model,
                temperature=0.0,
                max_tokens=200,
                response_format="json",
            )
        except Exception:
            _logger.warning(
                "Individual recognition LLM tiebreak call failed; falling back to "
                "the top-scoring candidate",
                exc_info=True,
            )
            return tied[0], False

        choice = ""
        payload = re.search(r"\{.*\}", response.content or "", re.S)
        if payload:
            try:
                choice = str(json.loads(payload.group(0)).get("individual_id", "")).strip()
            except (ValueError, TypeError):
                choice = ""

        if choice.lower() == "none":
            return None, True
        for candidate in tied:
            if candidate.individual_id == choice:
                return candidate, True

        _logger.warning(
            "Individual recognition LLM tiebreak returned an unusable choice %r; "
            "falling back to the top-scoring candidate",
            choice,
        )
        return tied[0], False

    @staticmethod
    def _describe_candidate(candidate: IndividualMatch) -> str:
        """One candidate line for the tiebreak prompt: title, description, classes, score."""
        description = (candidate.description or "").strip()
        detail = f" - {description}" if description else ""
        classes = ", ".join(candidate.class_ids) if candidate.class_ids else "none"
        return (
            f"- {candidate.individual_id}: {candidate.title}{detail} "
            f"(classes: {classes}; similarity {candidate.score:.2f})"
        )

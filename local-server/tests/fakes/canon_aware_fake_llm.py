"""
Canon-aware fake LLM provider for the pipeline test cycle.

Unlike `FakeLLMProvider`, which returns a single canned string regardless of input,
this fake looks at the user_prompt, detects which canon paper's source_text is
embedded in it, and returns that paper's `expected_relationships` as a properly-
shaped triple-extraction JSON response.

This lets the integration tests assert against real, paper-specific extraction
output without paying for LLM tokens. The fake is the deterministic substitute
for the real LLM in CI; the `@pytest.mark.real_llm` suite hits Anthropic via
prompt_cache for authentic validation.

Usage:
    fake = CanonAwareFakeLLMProvider(
        canon_dir="datafiles/canon/software_architecture",
    )
    # Drop into ExtractionService in place of FakeLLMProvider.

If a paper's source_text is not found in the user_prompt the fake returns an
empty triples list by default. Set `strict=True` to raise instead, which is
useful for catching prompt-construction regressions.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Literal

from domain.pipelines.ports import LLMResponse

_logger = logging.getLogger(__name__)


_PROVENANCE_WINDOW = 80  # chars of context to record per triple


class CanonAwareFakeLLMProvider:
    """
    Fake LLMProvider keyed on canon paper source_text.

    On init, walks `canon_dir/paper_*.json` and builds a lookup of
    (source_text_hash) → triple_response_json. On `complete()`, examines the
    user_prompt, finds the embedded source_text, and returns the matching
    response as the LLM content.
    """

    def __init__(
        self,
        canon_dir: str | Path,
        *,
        strict: bool = True,
        tokens_in: int = 1024,
        tokens_out: int = 512,
    ) -> None:
        self._canon_dir = Path(canon_dir)
        self._strict = strict
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
        self._lookup: dict[str, dict[str, Any]] = {}
        self._papers_by_name: dict[str, dict[str, Any]] = {}
        self._load_canon()

        # Inspectable test state, mirroring FakeLLMProvider.
        self.call_count: int = 0
        self.last_call_args: dict[str, Any] | None = None
        self.unmatched_prompts: list[str] = []
        self.available_models = [
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "google/gemini-3-flash-preview",
            "test-model",
        ]

    # ------------------------------------------------------------------ #
    # Canon loading                                                       #
    # ------------------------------------------------------------------ #

    def _load_canon(self) -> None:
        if not self._canon_dir.is_dir():
            raise FileNotFoundError(f"Canon directory not found: {self._canon_dir}")

        paper_files = sorted(self._canon_dir.glob("paper_*.json"))
        if not paper_files:
            raise FileNotFoundError(f"No paper_*.json fixtures found under {self._canon_dir}")

        for path in paper_files:
            paper = json.loads(path.read_text(encoding="utf-8"))
            name = paper.get("name") or path.stem.replace("paper_", "")
            source_text = paper.get("source_text", "")
            if not source_text:
                # A paper without source_text cannot be matched against any
                # prompt — silently skipping would invisibly break recall
                # tests. Raise so the corpus author sees the issue immediately.
                raise ValueError(
                    f"Canon paper {path.name!r} has empty source_text; "
                    "this would make the paper unmatchable by the fake LLM."
                )
            self._papers_by_name[name] = paper
            response_json = self._build_response_json(paper)
            key = self._hash_text(source_text)
            self._lookup[key] = response_json

    # ------------------------------------------------------------------ #
    # LLMProvider protocol                                                #
    # ------------------------------------------------------------------ #

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        self.call_count += 1
        self.last_call_args = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
            "timeout": timeout,
            "seed": seed,
        }

        response_json = self._match_prompt(user_prompt)
        if response_json is None:
            self.unmatched_prompts.append(user_prompt)
            # Always log so a prompt-construction regression surfaces in test
            # output even when strict=False masks it as an empty-triple result.
            _logger.warning(
                "CanonAwareFakeLLMProvider: no canon paper matched prompt "
                "(prefix=%r); returning %s",
                user_prompt[:120],
                "LookupError" if self._strict else "empty triples",
            )
            if self._strict:
                raise LookupError(
                    "CanonAwareFakeLLMProvider: no canon paper source_text "
                    "found inside user_prompt. Pass strict=False to fall "
                    "back to an empty triple list (only do this if your "
                    "test deliberately exercises the empty-LLM-response "
                    "path)."
                )
            response_json = {"triples": []}

        content = json.dumps(response_json)
        return LLMResponse(
            content=content,
            tokens_in=self._tokens_in,
            tokens_out=self._tokens_out,
            duration_ms=0.0,
            finish_reason="stop",
            model=model,
        )

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
        seed: int | None = None,
    ) -> LLMResponse:
        return self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )

    def is_model_available(self, model: str) -> bool:
        return model in self.available_models

    def list_available_models(self) -> list[str]:
        return list(self.available_models)

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def _match_prompt(self, user_prompt: str) -> dict[str, Any] | None:
        """
        Find which canon paper's source_text is embedded in the user_prompt.

        Strategy: substring search by source_text. The pipeline's user_prompt
        wraps the source_text in scaffolding (instructions, ontology context,
        formatting hints) so an exact hash match is unreliable. A direct
        `in` check is robust because the source_text is included verbatim.
        """
        for name, paper in self._papers_by_name.items():
            source_text = paper.get("source_text", "")
            if source_text and source_text in user_prompt:
                return self._lookup[self._hash_text(source_text)]
        return None

    def _build_response_json(self, paper: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a paper fixture's expected_relationships + expected_entities
        into the triple-JSON shape the orchestrator parses.
        """
        entities_by_id = {e["id"]: e for e in paper.get("expected_entities", [])}
        source_text = paper.get("source_text", "")
        triples: list[dict[str, Any]] = []

        for rel in paper.get("expected_relationships", []):
            subject_id = rel["subject"]
            predicate_id = rel["predicate"]
            object_id = rel["object"]

            subj_meta = entities_by_id.get(subject_id, {})
            obj_meta = entities_by_id.get(object_id, {})

            subject_payload = self._entity_payload(subject_id, subj_meta)
            object_payload = self._entity_payload(object_id, obj_meta)

            triples.append(
                {
                    "subject": subject_payload,
                    "predicate": {
                        "property_definition_id": predicate_id,
                        "label": predicate_id.replace("_", " "),
                    },
                    "object": object_payload,
                    "confidence": 0.95,
                    "provenance": self._provenance_for(source_text, subj_meta, obj_meta),
                }
            )

        return {"triples": triples}

    @staticmethod
    def _entity_payload(entity_id: str, meta: dict[str, Any]) -> dict[str, Any]:
        return {
            "kind": "individual",
            "id": entity_id,
            "label": meta.get("label", entity_id.replace("_", " ").title()),
        }

    @staticmethod
    def _provenance_for(
        source_text: str,
        subject_meta: dict[str, Any],
        object_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Locate the first textual mention of the subject in the source and
        record a small surrounding window. This produces realistic provenance
        without requiring per-triple offsets in the gold fixture.
        """
        if not source_text:
            return {"text_offset_start": 0, "text_offset_end": 0, "raw": ""}

        anchor = subject_meta.get("label") or subject_meta.get("context") or ""
        idx = source_text.find(anchor) if anchor else -1
        if idx < 0 and object_meta:
            anchor = object_meta.get("label") or ""
            idx = source_text.find(anchor) if anchor else -1
        if idx < 0:
            idx = 0

        end = min(len(source_text), idx + _PROVENANCE_WINDOW)
        return {
            "text_offset_start": idx,
            "text_offset_end": end,
            "raw": source_text[idx:end],
        }

    # ------------------------------------------------------------------ #
    # Diagnostics                                                         #
    # ------------------------------------------------------------------ #

    @property
    def loaded_paper_names(self) -> list[str]:
        return sorted(self._papers_by_name.keys())

    def response_for_paper(self, name: str) -> dict[str, Any]:
        """Inspect the canned response that would be returned for a paper."""
        paper = self._papers_by_name.get(name)
        if paper is None:
            raise KeyError(f"No paper named {name!r} loaded")
        return self._lookup[self._hash_text(paper["source_text"])]

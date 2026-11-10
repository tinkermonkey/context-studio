"""
DR's split claims and triage bench gold -> the dr_spec taxonomy's claims (#1521).

Documentation Robotics (DR) splits its enrichment notes into atomic claims
(`cli/scripts/spec-enrich/split-notes.ts`, `data/triage/claims.jsonl`), one JSON
object per line:

    {id: "<note_id>#<n>", note_id, layer, subject: "<spec node id>",
     kind: "node" | "relationships", text, category_hint,
     affected_ids: [spec node ids, "<node>.<attribute>", or relationship ids
                    "<source node>.<predicate>.<destination node>"],
     proposed_change}

and adjudicates some of them (`data/triage/bench-gold.jsonl`):

    {claim_id, validity, category, severity, fix_scope?, rationale, adjudicated_by?}

Every DR id is mapped to the Context Studio entity that carries it as a DR
external reference: node types to classes, relationship ids to property
definitions, and "<node>.<attribute>" to the class's attribute definition named
by its DR reference. Ids that map to nothing stay as `unresolved_refs`. The
claim's key is DR's claim id and its note ref DR's note id, so a re-import
replaces claims rather than adding them, and DR's gold becomes verdicts
(adjudicated_by "dr-bench-gold").
"""

from __future__ import annotations

import json
import lzma
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from adapters.interchange.dr_relationships import (
    DR_TAXONOMY_IDENTIFIER,
    dr_property_definitions,
    dr_relationship_id,
    dr_spec_classes,
)
from domain.ontology.ports import OntologyRepository
from domain.versioning.claims import (
    Claim,
    ClaimFilter,
    ClaimService,
    ClaimVerdict,
    NoteSource,
)

DR_BENCH_GOLD = "dr-bench-gold"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """The objects in a JSONL file, read through xz when the name ends in .xz."""
    opener: Any = lzma.open if path.suffix == ".xz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class DrIdResolver:
    """Map DR spec ids to the dr_spec taxonomy's entity ids."""

    def __init__(self, repo: OntologyRepository) -> None:
        self._repo = repo
        self._classes = dr_spec_classes(repo)
        self._properties = {k: p.id for k, p in dr_property_definitions(repo).items()}
        self._attributes: dict[str, dict[str, str]] = {}

    def resolve(self, dr_id: str) -> str | None:
        """The entity id for a node type, relationship or "<node>.<attribute>" id."""
        if dr_id in self._properties:
            return self._properties[dr_id]
        if dr_id in self._classes:
            return self._classes[dr_id]
        node_id, _, attribute = dr_id.rpartition(".")
        if node_id in self._classes:
            return self._attributes_of(node_id).get(attribute)
        return None

    def _attributes_of(self, node_id: str) -> dict[str, str]:
        if node_id not in self._attributes:
            self._attributes[node_id] = {
                name: attribute.id
                for attribute in self._repo.list_attribute_definitions(
                    class_id=self._classes[node_id], limit=None
                )
                if (name := dr_relationship_id(attribute.external_references))
            }
        return self._attributes[node_id]


@dataclass
class DrClaimsImport:
    """What an import stored."""

    claims: int = 0
    references: int = 0
    unresolved_references: int = 0
    unresolved: list[str] = field(default_factory=list)
    unresolved_subjects: list[str] = field(default_factory=list)
    verdicts: int = 0
    gold_without_claim: list[str] = field(default_factory=list)


def _claim(taxonomy_id: str, row: dict[str, Any], resolver: DrIdResolver) -> Claim:
    subject = row.get("subject")
    subject_id = resolver.resolve(subject) if subject else None
    affected, unresolved = [], []
    for dr_id in row.get("affected_ids") or []:
        entity_id = resolver.resolve(dr_id)
        if entity_id:
            affected.append(entity_id)
        else:
            unresolved.append(dr_id)
    if subject and subject_id is None:
        unresolved.insert(0, subject)
    return Claim(
        taxonomy_id=taxonomy_id,
        key=row["id"],
        text=row["text"],
        note_ref=row["note_id"],
        # DR's notes come from its maintainers' enrichment passes
        note_source=NoteSource.MAINTAINER,
        subject_id=subject_id,
        category_hint=row.get("category_hint") or None,
        affected_ids=affected,
        unresolved_refs=unresolved,
        proposed_change=row.get("proposed_change") or None,
    )


def _verdict(row: dict[str, Any]) -> ClaimVerdict:
    return ClaimVerdict(
        validity=row["validity"],
        adjudicated_by=DR_BENCH_GOLD,
        rationale=row.get("rationale") or "",
        category=row.get("category"),
        severity=row.get("severity"),
        fix_scope=row.get("fix_scope"),
    )


def import_dr_claims(
    claims: ClaimService,
    repo: OntologyRepository,
    claim_rows: Iterable[dict[str, Any]],
    gold_rows: Iterable[dict[str, Any]] = (),
) -> DrClaimsImport:
    """
    Store DR's claims on the dr_spec taxonomy and its gold as their verdicts.

    Raises:
        ValueError: If the DR spec has not been imported
    """
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        raise ValueError(f"No '{DR_TAXONOMY_IDENTIFIER}' taxonomy; import the DR spec first")
    resolver = DrIdResolver(repo)
    rows = list(claim_rows)
    stored = claims.submit(taxonomy.id, [_claim(taxonomy.id, row, resolver) for row in rows])
    result = DrClaimsImport(
        claims=len(stored),
        references=sum(len(c.affected_ids) + len(c.unresolved_refs) for c in stored),
        unresolved_references=sum(len(c.unresolved_refs) for c in stored),
        unresolved=sorted({ref for c in stored for ref in c.unresolved_refs}),
        unresolved_subjects=sorted(
            {
                row["subject"]
                for row, c in zip(rows, stored)
                if row.get("subject") and not c.subject_id
            }
        ),
    )
    gold = list(gold_rows)
    if gold:
        by_key = {
            c.key: c.id
            for c in claims.list_claims(
                ClaimFilter(taxonomy_id=taxonomy.id, keys=tuple(r["claim_id"] for r in gold))
            )
        }
        for row in gold:
            claim_id = by_key.get(row["claim_id"])
            if claim_id is None:
                result.gold_without_claim.append(row["claim_id"])
                continue
            claims.set_verdict(claim_id, _verdict(row))
            result.verdicts += 1
    return result

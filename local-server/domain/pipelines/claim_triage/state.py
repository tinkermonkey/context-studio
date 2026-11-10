"""
What the decision model reads about one claim, following DR's triage.ts
claimState: the claim, the definition pending for its subject (if any), then the
evidence pack built from the ontology (intent by context policy, attribute
peers, pair edges, predicate context).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Optional

from domain.ontology.entities import AttributeDefinition, Class, PropertyDefinition
from domain.ontology.evidence import ContextPolicy, EvidencePackBuilder
from domain.ontology.ports import OntologyRepository
from domain.versioning.claims import Claim


@dataclass
class _Named:
    """What a claim's ids name, split by kind."""

    classes: list[Class] = field(default_factory=list)
    properties: list[PropertyDefinition] = field(default_factory=list)
    attributes: list[AttributeDefinition] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)


class ClaimStateRenderer:
    """Renders a claim's state for the triage questions."""

    def __init__(self, repo: OntologyRepository, builder: EvidencePackBuilder) -> None:
        self._repo = repo
        self._builder = builder

    def render(
        self,
        claim: Claim,
        taxonomy_title: str,
        policy: ContextPolicy,
        pending_definition: Optional[Mapping[str, object]] = None,
    ) -> str:
        """
        The state text.

        Args:
            claim: The claim
            taxonomy_title: The taxonomy's title, for the heading
            policy: How much design intent the evidence pack includes
            pending_definition: The changed fields of the newest pending update
                to the subject in an open proposal, if there is one
        """
        named = self._named([claim.subject_id] if claim.subject_id else [], claim.affected_ids)
        subject_label = self._label(claim.subject_id) if claim.subject_id else "(none given)"
        affected = ", ".join(named.labels) or "(none given)"
        lines = [
            f"# Claim about the {taxonomy_title} taxonomy",
            f"Subject: {subject_label}",
            f"Claim: {claim.text}",
            f"Affected: {affected}",
        ]
        if claim.unresolved_refs:
            lines.append(f"Also names (not found): {', '.join(claim.unresolved_refs)}")
        lines.append(f"Proposed change: {claim.proposed_change or '(none given)'}")
        if pending_definition:
            lines += ["", "# Proposed definition (pending in an open proposal)"]
            lines += [f"{name}: {value}" for name, value in pending_definition.items()]
        pack = self._pack(claim, named, policy)
        if pack:
            lines += ["", "# The subject as it stands, and verified facts from the ontology", pack]
        return "\n".join(lines)

    def _pack(self, claim: Claim, named: _Named, policy: ContextPolicy) -> Optional[str]:
        """The evidence pack about the subject class, or the first class the claim names."""
        subject = self._subject_class(claim.subject_id, named)
        if subject is None:
            return None
        return self._builder.build(
            subject,
            named_class_ids=[c.id for c in named.classes if c.id != subject],
            relationship_type_ids=[p.id for p in named.properties],
            attributes=[(a.class_id, a.identifier) for a in named.attributes],
            policy=policy,
        ).text

    def _subject_class(self, subject_id: Optional[str], named: _Named) -> Optional[str]:
        if subject_id:
            if self._repo.get_class(subject_id):
                return subject_id
            prop = self._repo.get_property_definition(subject_id)
            if prop and prop.domain_class_id:
                return prop.domain_class_id
            attribute = self._repo.get_attribute_definition(subject_id)
            if attribute:
                return attribute.class_id
        if named.classes:
            return named.classes[0].id
        for prop in named.properties:
            if prop.domain_class_id:
                return prop.domain_class_id
        return named.attributes[0].class_id if named.attributes else None

    def _named(self, subject_ids: Sequence[str], affected_ids: Sequence[str]) -> _Named:
        named = _Named()
        for entity_id in [*subject_ids, *affected_ids]:
            if (cls := self._repo.get_class(entity_id)) is not None:
                if all(c.id != cls.id for c in named.classes):
                    named.classes.append(cls)
            elif (prop := self._repo.get_property_definition(entity_id)) is not None:
                named.properties.append(prop)
            elif (attribute := self._repo.get_attribute_definition(entity_id)) is not None:
                named.attributes.append(attribute)
        named.labels = [self._label(i) for i in affected_ids]
        return named

    def _label(self, entity_id: str) -> str:
        """A readable name for an id: identifier first, then title."""
        repo = self._repo
        if (cls := repo.get_class(entity_id)) is not None:
            return cls.identifier or cls.title
        if (prop := repo.get_property_definition(entity_id)) is not None:
            return prop.identifier or prop.title
        if (attribute := repo.get_attribute_definition(entity_id)) is not None:
            owner = repo.get_class(attribute.class_id)
            return f"{(owner.identifier or owner.title) if owner else '?'}.{attribute.identifier}"
        if (scheme := repo.get_concept_scheme(entity_id)) is not None:
            return scheme.identifier or scheme.title
        if (taxonomy := repo.get_taxonomy(entity_id)) is not None:
            return taxonomy.title
        return entity_id

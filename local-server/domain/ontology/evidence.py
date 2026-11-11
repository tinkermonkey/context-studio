"""
Evidence packs: the verifiable facts a decision about the ontology turns on.

A port of DR's `claimEvidence()` (`cli/scripts/spec-enrich/lib/intent.ts`) to
Context Studio's ontology, for any taxonomy. The pack is built by deterministic
lookups (no LLM) from the ids a decision names:

- attribute (class, identifier) -> how every class in that class's scheme
  declares the attribute, its own or inherited from an ancestor class
- classes (subject + named)     -> every relationship type between any two of
  them, both directions (the subject's own self-loops only when it is alone;
  the named classes' self-loops unless `include_named_self_loops=False`)
- relationship type ids         -> the predicate's meaning, every predicate
  joining the same pair and the reverse-direction predicates

Plus the design intent under a context policy: `summary` gives the taxonomy
summary, the scheme scope note and the subject class's definition; `full` adds
the taxonomy's charter (its vision); `none` gives no intent.

Size: rendered text is whitespace-collapsed; attribute definitions are clipped
to `DEFINITION_CLIP` characters, the taxonomy summary, scope note and class
definition to `INTENT_CLIP`, and attribute peers to `MAX_ATTRIBUTE_PEERS` rows
(the owner's row always kept). The charter on `full` is included whole and is
unbounded. Unlike DR, which clips raw text, whitespace is collapsed before
clipping, so a clipped definition can run a little further than DR's; the
facts are unchanged.

Predicate meanings come from an optional predicate catalog (DR's is the dr_spec
taxonomy's predicates, each one's description; see
`adapters.interchange.dr_relationships.dr_predicate_catalog`); without one, a
relationship type's own description is its meaning.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .entities import AttributeDefinition, Class, PropertyDefinition
from .exceptions import EntityNotFoundError
from .ports import OntologyRepository

DEFINITION_CLIP = 90
INTENT_CLIP = 300
MAX_ATTRIBUTE_PEERS = 25
NO_EVIDENCE = "(no structured evidence for the named ids)"


class ContextPolicy(str, Enum):
    """How much design intent a pack carries."""

    FULL = "full"
    SUMMARY = "summary"
    NONE = "none"


@dataclass(frozen=True)
class IntentEvidence:
    """What the taxonomy, scheme and class say they are for."""

    taxonomy_summary: str | None
    charter: str | None
    scheme_label: str
    scheme_scope_note: str | None
    class_label: str
    class_definition: str | None


@dataclass(frozen=True)
class AttributePeer:
    """One class's declaration of an attribute (its own, or an ancestor's)."""

    class_id: str
    class_label: str
    datatype: str
    allowed_values: tuple[str, ...] | None
    is_required: bool
    definition: str | None
    inherited_from_class_id: str | None = None
    inherited_from_label: str | None = None


@dataclass(frozen=True)
class AttributeEvidence:
    """How the classes in a scheme declare one attribute (at most MAX_ATTRIBUTE_PEERS)."""

    attribute_identifier: str
    concept_scheme_id: str
    scheme_label: str
    peers: tuple[AttributePeer, ...]
    omitted: int = 0


@dataclass(frozen=True)
class EdgeEvidence:
    """One relationship type with its predicate's meaning."""

    property_id: str
    identifier: str
    domain_class_id: str
    domain_label: str
    predicate: str
    range_class_id: str
    range_label: str
    meaning: str | None


@dataclass(frozen=True)
class PairEvidence:
    """Every relationship type between the named classes."""

    class_ids: tuple[str, ...]
    class_labels: tuple[str, ...]
    edges: tuple[EdgeEvidence, ...]


@dataclass(frozen=True)
class PredicateContext:
    """A named relationship type, the other predicates on its pair and the reverse ones."""

    edge: EdgeEvidence
    same_pair_predicates: tuple[str, ...]
    reverse_predicates: tuple[str, ...]


@dataclass(frozen=True)
class EvidencePack:
    """The structured evidence plus its compact text rendering."""

    subject_class_id: str
    policy: ContextPolicy
    intent: IntentEvidence | None
    attributes: tuple[AttributeEvidence, ...]
    pair: PairEvidence | None
    predicates: tuple[PredicateContext, ...]
    text: str


def _label(entity: Any) -> str:
    return entity.identifier or entity.title


def _predicate(prop: PropertyDefinition) -> str:
    return prop.canonical_predicate or prop.identifier


def _clip(text: str | None, limit: int | None = None) -> str | None:
    """`text` on one line (whitespace collapsed), cut to `limit` characters; None if empty."""
    flat = " ".join(text.split()) if text else ""
    return (flat[:limit].rstrip() if limit else flat) or None


def _edge_sort_key(edge: EdgeEvidence) -> tuple[str, ...]:
    return (edge.domain_label, edge.predicate, edge.range_label, edge.identifier, edge.property_id)


class EvidencePackBuilder:
    """Builds evidence packs from an ontology repository."""

    def __init__(
        self,
        repo: OntologyRepository,
        predicate_catalog: Mapping[str, Mapping[str, Any]] | None = None,
        include_named_self_loops: bool = True,
    ) -> None:
        """
        Args:
            repo: The ontology to read.
            predicate_catalog: Optional predicate id -> {"description", ...}. When
                given, it alone supplies predicate meanings (as in DR); otherwise
                a relationship type's description is its meaning.
            include_named_self_loops: Whether the pair section lists the named
                classes' self-loops. True matches DR's claimEvidence; the
                subject's own self-loops are listed only when it is alone.
        """
        self._repo = repo
        self._catalog = predicate_catalog
        self._include_named_self_loops = include_named_self_loops

    def build_for_relationship_type(
        self, property_id: str, policy: ContextPolicy = ContextPolicy.SUMMARY
    ) -> EvidencePack:
        """The pack for a decision about one relationship type: its domain is the subject."""
        prop = self._repo.get_property_definition(property_id)
        if prop is None:
            raise EntityNotFoundError("PropertyDefinition", property_id)
        if prop.domain_class_id is None or prop.range_class_id is None:
            raise ValueError(f"Relationship type '{property_id}' has no domain or range class")
        return self.build(
            prop.domain_class_id,
            named_class_ids=[prop.range_class_id],
            relationship_type_ids=[property_id],
            policy=policy,
        )

    def build_for_attribute(
        self,
        class_id: str,
        attribute_identifier: str,
        policy: ContextPolicy = ContextPolicy.SUMMARY,
    ) -> EvidencePack:
        """The pack for a decision about one attribute on a class."""
        return self.build(class_id, attributes=[(class_id, attribute_identifier)], policy=policy)

    def build(
        self,
        subject_class_id: str,
        named_class_ids: Sequence[str] = (),
        relationship_type_ids: Sequence[str] = (),
        attributes: Sequence[tuple[str, str]] = (),
        policy: ContextPolicy = ContextPolicy.SUMMARY,
    ) -> EvidencePack:
        """
        The pack for a decision about `subject_class_id` naming other ids.

        Args:
            subject_class_id: The class the decision is about.
            named_class_ids: Other classes it names (unknown ids are skipped).
            relationship_type_ids: Property definitions it names (unknown ids are skipped).
            attributes: (class id, attribute identifier) pairs it names.
            policy: How much design intent to include.
        """
        subject = self._repo.get_class(subject_class_id)
        if subject is None:
            raise EntityNotFoundError("Class", subject_class_id)
        policy = ContextPolicy(policy)
        classes: dict[str, Class] = {subject.id: subject}
        for class_id in named_class_ids:
            if class_id not in classes and (cls := self._repo.get_class(class_id)) is not None:
                classes[class_id] = cls
        outgoing = _OutgoingIndex(self._repo)

        intent = self._intent(subject, policy)
        attribute_evidence = tuple(
            evidence
            for class_id, identifier in attributes
            if (evidence := self._attribute(class_id, identifier)) is not None
        )
        pair = self._pair(subject.id, classes, outgoing)
        predicates = tuple(
            context
            for property_id in dict.fromkeys(relationship_type_ids)
            if (context := self._predicate_context(property_id, outgoing)) is not None
        )
        text = _render(intent, attribute_evidence, pair, predicates)
        return EvidencePack(
            subject_class_id=subject.id,
            policy=policy,
            intent=intent,
            attributes=attribute_evidence,
            pair=pair,
            predicates=predicates,
            text=text,
        )

    def _intent(self, subject: Class, policy: ContextPolicy) -> IntentEvidence | None:
        if policy is ContextPolicy.NONE:
            return None
        taxonomy = self._repo.get_taxonomy(subject.taxonomy_id)
        scheme = self._repo.get_concept_scheme(subject.concept_scheme_id)
        charter = taxonomy.vision if taxonomy and policy is ContextPolicy.FULL else None
        return IntentEvidence(
            taxonomy_summary=_clip(taxonomy.description, INTENT_CLIP) if taxonomy else None,
            charter=charter.strip() or None if charter else None,
            scheme_label=_label(scheme) if scheme else subject.concept_scheme_id,
            scheme_scope_note=_clip(scheme.description, INTENT_CLIP) if scheme else None,
            class_label=_label(subject),
            class_definition=_clip(subject.description, INTENT_CLIP),
        )

    def _attribute(self, class_id: str, identifier: str) -> AttributeEvidence | None:
        owner = self._repo.get_class(class_id)
        if owner is None:
            return None
        scheme = self._repo.get_concept_scheme(owner.concept_scheme_id)
        siblings = self._repo.list_classes(concept_scheme_id=owner.concept_scheme_id, limit=None)
        declarations = _Declarations(self._repo, identifier)
        peers = []
        for cls in sorted(siblings, key=lambda c: (_label(c), c.id)):
            found = declarations.of(cls)
            if found is None:
                continue
            attr, declarer = found
            inherited = declarer.id != cls.id
            peers.append(
                AttributePeer(
                    class_id=cls.id,
                    class_label=_label(cls),
                    datatype=str(getattr(attr.datatype, "value", attr.datatype)),
                    allowed_values=tuple(attr.allowed_values) if attr.allowed_values else None,
                    is_required=attr.is_required,
                    definition=_clip(attr.description, DEFINITION_CLIP),
                    inherited_from_class_id=declarer.id if inherited else None,
                    inherited_from_label=_label(declarer) if inherited else None,
                )
            )
        # The owner's row is always kept; the cap trims the other classes.
        others = [p for p in peers if p.class_id != owner.id]
        kept_others = {id(p) for p in others[: MAX_ATTRIBUTE_PEERS - (len(peers) - len(others))]}
        kept = [p for p in peers if p.class_id == owner.id or id(p) in kept_others]
        return AttributeEvidence(
            attribute_identifier=identifier,
            concept_scheme_id=owner.concept_scheme_id,
            scheme_label=_label(scheme) if scheme else owner.concept_scheme_id,
            peers=tuple(kept),
            omitted=len(peers) - len(kept),
        )

    def _pair(
        self, subject_id: str, classes: dict[str, Class], outgoing: "_OutgoingIndex"
    ) -> PairEvidence | None:
        alone = len(classes) == 1

        def listed(prop: PropertyDefinition) -> bool:
            if prop.range_class_id not in classes:
                return False
            if alone or prop.domain_class_id != prop.range_class_id:
                return True
            return prop.domain_class_id != subject_id and self._include_named_self_loops

        edges = [
            self._edge(prop, classes)
            for class_id in classes
            for prop in outgoing.of(class_id)
            if listed(prop)
        ]
        if alone and not edges:
            return None
        return PairEvidence(
            class_ids=tuple(classes),
            class_labels=tuple(_label(cls) for cls in classes.values()),
            edges=tuple(sorted(edges, key=_edge_sort_key)),
        )

    def _predicate_context(
        self, property_id: str, outgoing: "_OutgoingIndex"
    ) -> PredicateContext | None:
        prop = self._repo.get_property_definition(property_id)
        if prop is None or prop.domain_class_id is None or prop.range_class_id is None:
            return None
        classes = {
            cls.id: cls
            for class_id in (prop.domain_class_id, prop.range_class_id)
            if (cls := self._repo.get_class(class_id)) is not None
        }
        if len(classes) < (1 if prop.domain_class_id == prop.range_class_id else 2):
            return None
        same = [
            p for p in outgoing.of(prop.domain_class_id) if p.range_class_id == prop.range_class_id
        ]
        reverse = [
            p for p in outgoing.of(prop.range_class_id) if p.range_class_id == prop.domain_class_id
        ]
        return PredicateContext(
            edge=self._edge(prop, classes),
            same_pair_predicates=tuple(sorted(_predicate(p) for p in same)),
            reverse_predicates=tuple(sorted(_predicate(p) for p in reverse)),
        )

    def _edge(self, prop: PropertyDefinition, classes: Mapping[str, Class]) -> EdgeEvidence:
        predicate = _predicate(prop)
        if self._catalog is not None:
            meaning = (self._catalog.get(predicate) or {}).get("description")
        else:
            meaning = prop.description
        return EdgeEvidence(
            property_id=prop.id,
            identifier=prop.identifier,
            domain_class_id=prop.domain_class_id or "",
            domain_label=_label(classes[prop.domain_class_id]),
            predicate=predicate,
            range_class_id=prop.range_class_id or "",
            range_label=_label(classes[prop.range_class_id]),
            meaning=_clip(meaning),
        )


class _OutgoingIndex:
    """Each class's outgoing relationship types, read once per build."""

    def __init__(self, repo: OntologyRepository) -> None:
        self._repo = repo
        self._by_domain: dict[str, list[PropertyDefinition]] = {}

    def of(self, class_id: str) -> list[PropertyDefinition]:
        if class_id not in self._by_domain:
            self._by_domain[class_id] = self._repo.list_property_definitions(
                domain_class_id=class_id, limit=None
            )
        return self._by_domain[class_id]


class _Declarations:
    """Where a class gets one attribute: itself, else its nearest ancestor declaring it."""

    def __init__(self, repo: OntologyRepository, identifier: str) -> None:
        self._repo = repo
        self._identifier = identifier
        self._own: dict[str, AttributeDefinition | None] = {}

    def _declared_by(self, class_id: str) -> AttributeDefinition | None:
        if class_id not in self._own:
            self._own[class_id] = next(
                (
                    attr
                    for attr in self._repo.list_attribute_definitions(class_id=class_id, limit=None)
                    if attr.identifier == self._identifier
                ),
                None,
            )
        return self._own[class_id]

    def of(self, cls: Class) -> tuple[AttributeDefinition, Class] | None:
        seen: set[str] = set()
        current: Class | None = cls
        while current is not None and current.id not in seen:
            seen.add(current.id)
            if (attr := self._declared_by(current.id)) is not None:
                return attr, current
            parent_id = current.parent_class_id
            current = self._repo.get_class(parent_id) if parent_id else None
        return None


def _render_intent(intent: IntentEvidence) -> str:
    lines = ["Design intent:"]
    if intent.taxonomy_summary:
        lines.append(f"  Taxonomy summary: {intent.taxonomy_summary}")
    if intent.scheme_scope_note:
        lines.append(f"  Scheme {intent.scheme_label} scope: {intent.scheme_scope_note}")
    if intent.class_definition:
        lines.append(f"  Class {intent.class_label} definition: {intent.class_definition}")
    if intent.charter:
        lines.append(f"  Charter:\n{intent.charter}")
    return "\n".join(lines) if len(lines) > 1 else ""


def _render_attribute(evidence: AttributeEvidence) -> str:
    rows = []
    for peer in evidence.peers:
        enum = f" enum[{'|'.join(peer.allowed_values)}]" if peer.allowed_values else ""
        definition = (
            f" desc={json.dumps(peer.definition, ensure_ascii=False)}"
            if peer.definition
            else " (no description)"
        )
        inherited = (
            f" (inherited from {peer.inherited_from_label})" if peer.inherited_from_label else ""
        )
        rows.append(
            f"  {peer.class_label}.{evidence.attribute_identifier}: type={peer.datatype}{enum}"
            f" required={str(peer.is_required).lower()}{definition}{inherited}"
        )
    if evidence.omitted:
        rows.append(f"  (+{evidence.omitted} more)")
    count = len(evidence.peers) + evidence.omitted
    return (
        f"Attribute '{evidence.attribute_identifier}' as declared across scheme "
        f"{evidence.scheme_label} ({count} classes):\n" + ("\n".join(rows) or "  (none)")
    )


def _render_edge(edge: EdgeEvidence) -> str:
    named = f" [{edge.identifier}]" if edge.identifier != edge.predicate else ""
    return f"{edge.domain_label} --[{edge.predicate}]--> {edge.range_label}{named}"


def _render_pair(pair: PairEvidence) -> str:
    rows = [f"  {_render_edge(e)}  ({e.predicate}: {e.meaning or '?'})" for e in pair.edges]
    return (
        f"Relationship types between {', '.join(pair.class_labels)} "
        f"(exact list, {len(rows)} types):\n" + ("\n".join(rows) or "  (none)")
    )


def _render_predicate(context: PredicateContext) -> str:
    edge = context.edge
    if edge.domain_class_id == edge.range_class_id:
        reverse = "reverse direction: same as above (self-loop)"
    else:
        reverse = (
            f"reverse direction {edge.range_label} -> {edge.domain_label}: "
            f"[{', '.join(context.reverse_predicates) or 'none'}]"
        )
    return (
        f"Relationship type {_render_edge(edge)}: predicate {edge.predicate} "
        f"({edge.meaning or '?'}); all predicates {edge.domain_label} -> {edge.range_label}: "
        f"[{', '.join(context.same_pair_predicates)}]; {reverse}"
    )


def _render(
    intent: IntentEvidence | None,
    attributes: Sequence[AttributeEvidence],
    pair: PairEvidence | None,
    predicates: Sequence[PredicateContext],
) -> str:
    blocks = [_render_intent(intent)] if intent else []
    blocks += [_render_attribute(a) for a in attributes]
    blocks += [_render_pair(pair)] if pair else []
    blocks += [_render_predicate(p) for p in predicates]
    return "\n\n".join(b for b in blocks if b) or NO_EVIDENCE

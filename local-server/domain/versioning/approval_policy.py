"""
Approval policy: what a proposal on a taxonomy may apply on its own.

A policy is a list of auto-apply rules and a minimum probability. A rule
matches an operation when every key it sets matches:

- op: create, update, move or delete
- kind: the kind of entity
- class: a class id or identifier the operation's entity is typed by (an
  individual's classes, an attribute's class, or the class itself)
- scope: editorial, additive or breaking

An entity typed by several classes needs every one of them covered: by a
matching rule naming that class, or by a matching rule with no class at all.
For an update that is the entity's current classes plus any it would gain.

Hard rules beat the policy:

- breaking operations (deletes among them) and taxonomy creates never auto-apply;
- a change to a taxonomy's vision never auto-applies: it is the charter
  proposals are judged against;
- an operation auto-applies only if its target and every entity it points at
  are inside the proposal's taxonomy (property definitions are global, so
  changing one never auto-applies, though a relationship may use one);
- an operation that points at a "$ref" auto-applies only if the create it
  points at does too;
- with no policy, nothing auto-applies.

The policy is set by a person through the REST API; it is never exposed as an
agent tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional, Sequence

from domain.ontology.exceptions import EntityNotFoundError
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationType,
    ProposedOperation,
)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.versioning.ports import ApprovalPolicyRepository

_RULE_KEYS = frozenset({"op", "kind", "class", "scope"})
_POLICY_KEYS = frozenset({"auto_apply", "min_probability"})
_REF_PREFIX = "$"


@dataclass(frozen=True)
class AutoApplyRule:
    """
    Operations matching every key set here may auto-apply.

    Attributes:
        op: Only this operation type
        kind: Only this kind of entity
        class_key: Only entities typed by this class (its id or identifier)
        scope: Only this scope
    """

    op: Optional[OperationType] = None
    kind: Optional[OperationKind] = None
    class_key: Optional[str] = None
    scope: Optional[ChangeScope] = None

    def __post_init__(self) -> None:
        if self.op is None and self.kind is None and self.class_key is None and self.scope is None:
            raise ValueError("An auto-apply rule needs at least one of op, kind, class, scope")

    def matches(self, operation: ProposedOperation) -> bool:
        """Whether the op, kind and scope this rule sets match (its class is checked per class)."""
        return (
            (self.op is None or operation.op is self.op)
            and (self.kind is None or operation.kind is self.kind)
            and (self.scope is None or operation.scope is self.scope)
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutoApplyRule:
        """
        Parse a rule like {"op": "create", "kind": "individual", "class": "house_activity"}.

        Raises:
            ValueError: For an unknown key or value, an empty rule, or a rule the
                hard rules mean can never match
        """
        if not isinstance(data, dict):
            raise ValueError("An auto-apply rule must be an object")
        unknown = sorted(set(data) - _RULE_KEYS)
        if unknown:
            raise ValueError(f"Unknown auto-apply rule keys {unknown}")
        class_key = data.get("class")
        if class_key is not None and (not isinstance(class_key, str) or not class_key):
            raise ValueError("A rule's class must be a class id or identifier")
        rule = cls(
            op=OperationType(data["op"]) if data.get("op") is not None else None,
            kind=OperationKind(data["kind"]) if data.get("kind") is not None else None,
            class_key=class_key,
            scope=ChangeScope(data["scope"]) if data.get("scope") is not None else None,
        )
        never = rule._never_matches()
        if never:
            raise ValueError(f"Auto-apply rule {data} can never match: {never}")
        return rule

    def _never_matches(self) -> Optional[str]:
        """Why the hard rules mean this rule can never match, if they do."""
        if self.op in (OperationType.DELETE, OperationType.MOVE):
            return f"a {self.op.value} is breaking and never auto-applies"
        if self.scope is ChangeScope.BREAKING:
            return "breaking operations never auto-apply"
        if self.kind is OperationKind.PROPERTY:
            return "property definitions are global and never auto-apply"
        if self.kind is OperationKind.TAXONOMY and self.op is OperationType.CREATE:
            return "taxonomy creates never auto-apply"
        return None

    def to_dict(self) -> dict[str, str]:
        """The rule's JSON form, with only the keys it sets."""
        found = {
            "op": self.op.value if self.op else None,
            "kind": self.kind.value if self.kind else None,
            "class": self.class_key,
            "scope": self.scope.value if self.scope else None,
        }
        return {key: value for key, value in found.items() if value is not None}


@dataclass(frozen=True)
class ApprovalPolicy:
    """
    A taxonomy's approval policy.

    Attributes:
        taxonomy_id: The taxonomy it governs
        auto_apply: Rules; an operation matching any of them may auto-apply
        min_probability: An operation also needs at least this probability
            (one without a probability passes only a minimum of 0)
    """

    taxonomy_id: str
    auto_apply: tuple[AutoApplyRule, ...] = field(default_factory=tuple)
    min_probability: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_probability <= 1.0:
            raise ValueError("min_probability must be between 0 and 1")

    def allows(self, operation: ProposedOperation, classes: Sequence[set[str]]) -> bool:
        """
        Whether this operation may auto-apply: never a breaking one, a delete, a
        taxonomy create or a change to a taxonomy's vision; otherwise when it is
        probable enough and matching rules cover it.

        Args:
            operation: The operation
            classes: One set of keys (id and identifier) per class the entity
                will be typed by; an empty set for a class no rule can name
        """
        if operation.scope is ChangeScope.BREAKING or operation.op is OperationType.DELETE:
            return False
        if operation.kind is OperationKind.TAXONOMY and operation.op is OperationType.CREATE:
            return False
        if operation.kind is OperationKind.TAXONOMY and "vision" in operation.fields:
            # The vision is the charter proposals are judged against: a person
            # always decides on a change to it, however editorial.
            return False
        probability = operation.probability if operation.probability is not None else 0.0
        if probability < self.min_probability:
            return False
        matching = [rule for rule in self.auto_apply if rule.matches(operation)]
        if any(rule.class_key is None for rule in matching):
            return True
        named = {rule.class_key for rule in matching}
        return bool(classes) and all(keys & named for keys in classes)

    @classmethod
    def from_rules(cls, taxonomy_id: str, rules: dict[str, Any]) -> ApprovalPolicy:
        """
        Parse the rules JSON: {"auto_apply": [...], "min_probability": 0}.

        Raises:
            ValueError: For unknown keys or invalid values
        """
        if not isinstance(rules, dict):
            raise ValueError("Approval policy rules must be an object")
        unknown = sorted(set(rules) - _POLICY_KEYS)
        if unknown:
            raise ValueError(f"Unknown approval policy keys {unknown}")
        auto_apply = rules.get("auto_apply") or []
        if not isinstance(auto_apply, list):
            raise ValueError("auto_apply must be a list of rules")
        min_probability = rules.get("min_probability", 0)
        if isinstance(min_probability, bool) or not isinstance(min_probability, (int, float)):
            raise ValueError("min_probability must be a number")
        return cls(
            taxonomy_id=taxonomy_id,
            auto_apply=tuple(AutoApplyRule.from_dict(rule) for rule in auto_apply),
            min_probability=float(min_probability),
        )

    def to_rules(self) -> dict[str, Any]:
        """The rules JSON this policy is stored as."""
        return {
            "auto_apply": [rule.to_dict() for rule in self.auto_apply],
            "min_probability": self.min_probability,
        }


def auto_apply_ids(
    policy: Optional[ApprovalPolicy],
    operations: Iterable[ProposedOperation],
    classes: Callable[[ProposedOperation], Sequence[set[str]]],
    inside_taxonomy: Callable[[ProposedOperation], bool],
    *,
    id_fields: frozenset[str],
) -> list[str]:
    """
    The operations a policy lets apply as soon as they are proposed, in seq order.

    An operation that points at a "$ref" qualifies only if the create it points
    at does too, so it never fails for want of an entity it depends on.

    Args:
        policy: The taxonomy's policy, or None (then nothing auto-applies)
        operations: The proposal's operations
        classes: Per class the operation's entity will be typed by, its keys
            (see ApprovalPolicy.allows)
        inside_taxonomy: Whether the operation's target and every existing
            entity it points at belong to the policy's taxonomy alone
        id_fields: The fields whose values name entities; only these can hold a
            "$ref" (a title like "$5 attic" is text)
    """
    if policy is None:
        return []
    chosen: list[str] = []
    applied_refs: set[str] = set()
    for operation in sorted(operations, key=lambda o: o.seq):
        if not policy.allows(operation, classes(operation)):
            continue
        if not _refs(operation.fields, id_fields) <= applied_refs:
            continue
        if not inside_taxonomy(operation):
            continue
        chosen.append(operation.id)
        if operation.ref:
            applied_refs.add(operation.ref)
    return chosen


def _refs(fields: dict[str, Any], id_fields: frozenset[str]) -> set[str]:
    """The refs ("$name" values) an operation's id fields point at, without the "$"."""
    found: set[str] = set()
    for name, value in fields.items():
        if name not in id_fields:
            continue
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str) and item.startswith(_REF_PREFIX) and len(item) > 1:
                found.add(item[1:])
    return found


class ApprovalPolicyService:
    """Read and set a taxonomy's approval policy."""

    def __init__(self, policies: ApprovalPolicyRepository, ontology_repo: OntologyRepository):
        self._policies = policies
        self._repo = ontology_repo

    def get(self, taxonomy_id: str) -> ApprovalPolicy:
        """
        The taxonomy's policy; an empty one (nothing auto-applies) if none is set.

        Raises:
            EntityNotFoundError: If the taxonomy does not exist
        """
        self._require_taxonomy(taxonomy_id)
        return self._policies.get(taxonomy_id) or ApprovalPolicy(taxonomy_id=taxonomy_id)

    def set(self, taxonomy_id: str, rules: dict[str, Any]) -> ApprovalPolicy:
        """
        Replace the taxonomy's policy with these rules.

        Raises:
            EntityNotFoundError: If the taxonomy does not exist
            ValueError: If the rules are invalid
        """
        self._require_taxonomy(taxonomy_id)
        return self._policies.save(ApprovalPolicy.from_rules(taxonomy_id, rules))

    def _require_taxonomy(self, taxonomy_id: str) -> None:
        if self._repo.get_taxonomy(taxonomy_id) is None:
            raise EntityNotFoundError("Taxonomy", taxonomy_id)

"""
Whether a relationship fits its type's domain and range (#1574).

An end fits a class when one of its classes (an individual's classes, or a
class end itself) is that class or a subclass of it. A type without a domain
(or range) accepts any source (or target), and an end with no classes is open:
nothing says it doesn't fit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from domain.ontology.entities import PropertyDefinition
    from domain.ontology.ports import OntologyRepository


class RelationshipFit:
    """Checks relationship ends against types, caching class ancestry and titles."""

    def __init__(self, repo: OntologyRepository) -> None:
        self._repo = repo
        self._ancestors: dict[str, frozenset[str]] = {}
        self._titles: dict[str, str] = {}

    def misfit(
        self,
        prop: PropertyDefinition,
        source_class_ids: Iterable[str],
        target_class_ids: Iterable[str],
    ) -> str | None:
        """
        Why a relationship of the type between ends of these classes breaks its
        domain or range ("target is Place, not Room"); None when it fits.
        """
        for end, class_id, class_ids in (
            ("source", prop.domain_class_id, tuple(source_class_ids)),
            ("target", prop.range_class_id, tuple(target_class_ids)),
        ):
            if class_ids and not self.accepts(class_id, class_ids):
                titles = " / ".join(self.class_title(c) for c in class_ids)
                return f"{end} is {titles}, not {self.class_title(class_id)}"  # type: ignore[arg-type]
        return None

    def accepts(self, class_id: str | None, class_ids: Iterable[str]) -> bool:
        """Whether an end of these classes fits the class (None: any end fits)."""
        if class_id is None:
            return True
        return any(class_id in self.ancestors_of(c) for c in class_ids)

    def ancestors_of(self, class_id: str) -> frozenset[str]:
        """The class and every class above it."""
        if class_id not in self._ancestors:
            seen: list[str] = []
            current: str | None = class_id
            while current is not None and current not in seen:
                seen.append(current)
                cls = self._repo.get_class(current)
                current = cls.parent_class_id if cls is not None else None
            self._ancestors[class_id] = frozenset(seen)
        return self._ancestors[class_id]

    def class_title(self, class_id: str) -> str:
        """A class's title (its id when it is gone)."""
        if class_id not in self._titles:
            cls = self._repo.get_class(class_id)
            self._titles[class_id] = cls.title if cls is not None else class_id
        return self._titles[class_id]

    def end_class_ids(self, entity_id: str) -> tuple[str, ...] | None:
        """An existing end's classes: an individual's, or a class end itself; None if it is gone."""
        individual = self._repo.get_individual(entity_id)
        if individual is not None:
            return tuple(individual.class_ids)
        return (entity_id,) if self._repo.get_class(entity_id) is not None else None

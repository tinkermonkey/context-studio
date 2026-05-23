"""
External knowledge source adapters for schema node grounding.

Wraps existing reference sources (DBpedia, ConceptNet) and queries them
for candidates that match a given label.
"""

from adapters.reference.grounding.adapter import GroundingAdapter

__all__ = ["GroundingAdapter"]

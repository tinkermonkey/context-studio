"""Shared result type returned by all pipeline apply services."""

from dataclasses import dataclass


@dataclass
class ApplyResult:
    """Counts of ontology entities created or skipped during a pipeline apply operation."""

    classes_created: int = 0
    classes_skipped: int = 0
    properties_created: int = 0
    properties_skipped: int = 0
    relationships_created: int = 0
    relationships_skipped: int = 0
    individuals_created: int = 0
    individuals_skipped: int = 0

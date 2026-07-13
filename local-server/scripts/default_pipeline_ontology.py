"""
Shared per-context ontology construction for the `default` LLM pipeline's
record + replay paths.

The default-pipeline cassette key hashes the extraction prompt, and the ONLY
ontology-derived value in that prompt is ``ontology.title`` (see
``domain/extraction/services.py::_build_triple_extraction_prompt`` — the user
prompt's last line is ``Ontology: {ontology.title}``). So the recorder
(``scripts/record_default_cassettes.py``) and the tournament replay
(``scripts/quality_tournament._make_default_variant``) MUST resolve each
scenario to an ontology with the SAME title, or replay misses with
``CassetteStaleError``. Both paths build their ontologies through this single
resolver so they cannot drift apart again (a prior divergence — the recorder
using conftest's "Placeholder Ontology"/"Documentation Robotics" while the
tournament hand-built a "Test Ontology" — is exactly what broke replay).

Kept out of the tournament/recorder modules (and imported lazily inside the
methods) so importing this module is cheap and free of pytest-conftest import
side effects until an ontology is actually built.
"""

from __future__ import annotations

from typing import Any

from tests.integration.pipelines._harness.dataset_split import OntologyContext

# Identifier of the placeholder taxonomy built by
# ``conftest._build_placeholder_ontology`` (title "Placeholder Ontology").
_PLACEHOLDER_TAXONOMY_IDENTIFIER = "placeholder"


def dr_spec_available() -> bool:
    """
    True when the DR spec checkout exists, so its ontology can be built.

    ``conftest._build_dr_spec_ontology`` calls ``pytest.skip()`` when the spec
    is absent — which would raise ``Skipped`` outside a test and crash a
    tournament run. Callers gate DR-context scenarios on this (the recorder
    skips them; the tournament declines to register the default variants).
    """
    from tests.integration.pipelines import conftest

    return conftest._find_dr_spec_dir() is not None


class DefaultPipelineOntologyResolver:
    """
    Build and cache the ``(repo, taxonomy, index)`` a scenario's default-pipeline
    run grounds against, keyed by ``OntologyContext``.

    Uses the same conftest builders on both the record and replay paths so the
    resolved ``ontology.title`` — the only ontology input to the cassette prompt
    hash — is identical. One instance is reused across a whole run so each
    context's ontology is built at most once.
    """

    def __init__(self) -> None:
        self._cache: dict[OntologyContext, tuple[Any, Any, Any]] = {}

    def get(self, context: OntologyContext) -> tuple[Any, Any, Any]:
        """Return ``(ontology_repo, taxonomy, schema_index)`` for ``context``."""
        if context not in self._cache:
            from scripts.dr_ontology_loader import DR_TAXONOMY_IDENTIFIER
            from tests.integration.pipelines import conftest

            builder = {
                OntologyContext.PLACEHOLDER: conftest._build_placeholder_ontology,
                OntologyContext.DR_SPEC: conftest._build_dr_spec_ontology,
            }[context]
            identifier = {
                OntologyContext.PLACEHOLDER: _PLACEHOLDER_TAXONOMY_IDENTIFIER,
                OntologyContext.DR_SPEC: DR_TAXONOMY_IDENTIFIER,
            }[context]
            repo, index = builder()
            taxonomy = repo.get_by_identifier(identifier)
            self._cache[context] = (repo, taxonomy, index)
        return self._cache[context]

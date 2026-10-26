"""
Integration tests for the chat's workspace context (#1336): the model sees each
taxonomy's one-paragraph summary up front, and fetches the vision with tools.
"""

from adapters.chat.context import OntologyWorkspaceContext
from tests.integration.chat.conftest import DR_VISION, TAXONOMY_ID


async def test_summary_lists_each_taxonomy_with_its_summary(dr_workspace):
    context = OntologyWorkspaceContext(dr_workspace.ontology)

    summary = await context.summarize()

    assert "- Documentation Robotics: Architecture model layers" in summary
    assert DR_VISION not in summary


async def test_long_summaries_are_shortened(dr_workspace):
    dr_workspace.ontology.update_taxonomy(TAXONOMY_ID, description="word " * 200)
    context = OntologyWorkspaceContext(dr_workspace.ontology)

    summary = await context.summarize()

    line = next(x for x in summary.splitlines() if x.startswith("- Documentation Robotics"))
    assert len(line) < 450 and line.endswith("…")


async def test_taxonomy_without_a_summary_is_listed_by_title(dr_workspace):
    dr_workspace.ontology.create_taxonomy(title="House")
    context = OntologyWorkspaceContext(dr_workspace.ontology)

    summary = await context.summarize()

    assert "\n- House" in summary

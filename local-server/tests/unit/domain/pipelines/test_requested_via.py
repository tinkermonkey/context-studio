"""Only a mirrored taxonomy's client, over MCP, may run a refinement on it (#1516)."""

import pytest

from domain.ontology.entities import Taxonomy
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.requested_via import REQUESTED_VIA, RequestedVia, ensure_may_propose_to


def taxonomy(mirrored: bool) -> Taxonomy:
    return Taxonomy(id="t", title="DR", identifier="dr", mirrored=mirrored)


@pytest.mark.parametrize("via", [None, *RequestedVia])
def test_any_caller_may_refine_a_taxonomy_that_is_not_mirrored(via):
    ensure_may_propose_to(taxonomy(False), {REQUESTED_VIA: via} if via else {})


def test_the_client_over_mcp_may_refine_a_mirrored_taxonomy():
    ensure_may_propose_to(taxonomy(True), {REQUESTED_VIA: RequestedVia.MCP.value})


@pytest.mark.parametrize("via", [RequestedVia.CHAT, RequestedVia.API])
def test_chat_and_the_api_may_not_refine_a_mirrored_taxonomy(via):
    with pytest.raises(PipelineInputError, match=f"only the client.*came from {via.value}"):
        ensure_may_propose_to(taxonomy(True), {REQUESTED_VIA: via.value})


def test_a_run_naming_no_caller_may_not_refine_a_mirrored_taxonomy():
    with pytest.raises(PipelineInputError, match="names no caller"):
        ensure_may_propose_to(taxonomy(True), {})

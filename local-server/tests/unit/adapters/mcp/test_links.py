"""Unit tests for MCP entity page links and the loopback host check."""

import re
from pathlib import Path

import pytest

from adapters.mcp.links import ENTITY_PAGE_PREFIX, PROPOSAL_PAGE_PREFIX, EntityLinks
from adapters.mcp.server import is_loopback_host
from domain.chat.value_objects import EntityRef

ENTITY_PATHS_TS = Path(__file__).resolve().parents[5] / "ux" / "src" / "lib" / "entityPaths.ts"


def test_page_prefixes_match_the_ui_routes():
    """The prefixes mirror ux/src/lib/entityPaths.ts; a renamed UI route must fail here."""
    source = ENTITY_PATHS_TS.read_text()
    block = re.search(r"ENTITY_PAGE_PREFIX[^{]*\{(?P<body>[^}]*)\}", source)
    assert block is not None, "ENTITY_PAGE_PREFIX not found in entityPaths.ts"
    ui_prefixes = dict(re.findall(r'(\w+):\s*"([^"]+)"', block.group("body")))

    assert ui_prefixes == ENTITY_PAGE_PREFIX


def test_url_for_a_class_page():
    links = EntityLinks("http://localhost:3100/")

    url = links.url(EntityRef(id="abc-1", kind="class", title="Operation"))

    assert url == "http://localhost:3100/app/schema/classes/abc-1"


def test_url_for_a_proposal_review_page():
    links = EntityLinks("http://localhost:3100")

    url = links.url(EntityRef(id="prop 1", kind="proposal", title="Clarify classes"))

    assert PROPOSAL_PAGE_PREFIX == "/app/proposals"
    assert url == "http://localhost:3100/app/proposals/prop%201"


def test_kinds_without_a_page_get_no_url():
    links = EntityLinks("http://localhost:3100")

    assert links.url(EntityRef(id="p-1", kind="property", title="realizes")) is None


@pytest.mark.parametrize("base", [None, ""])
def test_links_are_off_without_a_base_url(base):
    links = EntityLinks(base)
    ref = EntityRef(id="t-1", kind="taxonomy", title="House")

    assert links.url(ref) is None
    assert links.block([ref]) == ""


def test_block_lists_each_linkable_entity():
    links = EntityLinks("http://localhost:3100")

    block = links.block(
        [
            EntityRef(id="t-1", kind="taxonomy", title="House"),
            EntityRef(id="p-1", kind="property", title="part_of"),
        ]
    )

    assert block == (
        "\n\nPages in Context Studio:\n"
        "- House (taxonomy): http://localhost:3100/app/schema/taxonomies/t-1"
    )


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("127.0.0.2", True),
        ("0.0.0.0", False),
        ("192.168.1.20", False),
        ("example.com", False),
    ],
)
def test_loopback_hosts(host, expected):
    assert is_loopback_host(host) is expected

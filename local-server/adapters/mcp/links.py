"""
Links from MCP tool results to the UI's entity pages.

The page prefixes mirror `ux/src/lib/entityPaths.ts`; a test pins them, so a
renamed route fails the build rather than handing out dead links.
"""

from __future__ import annotations

from typing import Optional, Sequence
from urllib.parse import quote

from domain.chat.value_objects import EntityRef

ENTITY_PAGE_PREFIX: dict[str, str] = {
    "taxonomy": "/app/schema/taxonomies",
    "scheme": "/app/schema/schemes",
    "class": "/app/schema/classes",
    "individual": "/app/data/individuals",
}


class EntityLinks:
    """Builds UI page links for the entities a tool result mentions."""

    def __init__(self, ui_base_url: Optional[str]) -> None:
        """
        Args:
            ui_base_url: Base URL of the UI (e.g. http://localhost:3100); None or
                empty disables links
        """
        self._base = (ui_base_url or "").rstrip("/")

    def url(self, ref: EntityRef) -> Optional[str]:
        """The page URL for an entity, or None if it has no page or links are off."""
        prefix = ENTITY_PAGE_PREFIX.get(ref.kind)
        if not self._base or prefix is None:
            return None
        return f"{self._base}{prefix}/{quote(ref.id, safe='')}"

    def block(self, refs: Sequence[EntityRef]) -> str:
        """A short text block listing page links, or '' when there are none."""
        lines = []
        for ref in refs:
            url = self.url(ref)
            if url:
                lines.append(f"- {ref.title} ({ref.kind}): {url}")
        if not lines:
            return ""
        return "\n\nPages in Context Studio:\n" + "\n".join(lines)

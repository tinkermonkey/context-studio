"""
Chat adapters for settings and workspace context.

ConfigChatSettings reads the `chat` section of config.json on every call, so a
change saved in Settings applies to the next turn without a restart.
OntologyWorkspaceContext describes the workspace and the viewed entity to the
model.
"""

from __future__ import annotations

from typing import Optional

from adapters.chat.tools import EntityResolver, kind_of, shortened
from config import ConfigurationManager
from domain.chat.value_objects import PageContext
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.services import OntologyService
from utils.async_executor import run_sync_in_executor

# Taxonomies named in the workspace summary.
_SUMMARY_TAXONOMIES = 20
# Each taxonomy's one-paragraph summary is cut to this length in the workspace summary.
_TAXONOMY_SUMMARY_CHARS = 400


class ConfigChatSettings:
    """ChatSettings port over config.json."""

    def __init__(self, config_manager: ConfigurationManager) -> None:
        self._config = config_manager

    def model(self) -> str:
        return self._config.get_settings().chat.model

    def max_tool_rounds(self) -> int:
        return self._config.get_settings().chat.max_tool_rounds


class OntologyWorkspaceContext:
    """WorkspaceContext port over the ontology service."""

    def __init__(self, ontology: OntologyService) -> None:
        self._ontology = ontology
        self._resolver = EntityResolver(ontology)

    async def summarize(self) -> str:
        return await run_sync_in_executor(self._summarize)

    async def describe_page(self, page_context: PageContext) -> Optional[str]:
        return await run_sync_in_executor(self._describe_page, page_context)

    def _summarize(self) -> str:
        taxonomies = self._ontology.list_taxonomies(limit=_SUMMARY_TAXONOMIES, sort_by="title")
        counts = (
            f"taxonomies {self._ontology.count_taxonomies()},"
            f" concept schemes {self._ontology.count_concept_schemes()},"
            f" classes {self._ontology.count_classes()},"
            f" individuals {self._ontology.count_individuals()},"
            f" relationships {self._ontology.count_relationships()},"
            f" relationship types {self._ontology.count_property_definitions()}"
        )
        summary = f"Workspace counts: {counts}."
        if taxonomies:
            lines = [
                (
                    f"- {t.title}: {shortened(t.description, _TAXONOMY_SUMMARY_CHARS)}"
                    if t.description
                    else f"- {t.title}"
                )
                for t in taxonomies
            ]
            summary += " Taxonomies, with their one-paragraph summaries:\n" + "\n".join(lines)
        return summary

    def _describe_page(self, page_context: PageContext) -> Optional[str]:
        if not page_context.entity_id:
            return f"The user is on the {page_context.route} page."
        try:
            entity = self._resolver.get(page_context.entity_id)
        except EntityNotFoundError:
            return f"The user is on the {page_context.route} page."
        kind = kind_of(entity)
        return (
            f"The user is viewing the {kind} “{entity.title}”"
            f" (link: entity:{kind}/{entity.id}). Questions about “this”"
            " likely refer to it."
        )

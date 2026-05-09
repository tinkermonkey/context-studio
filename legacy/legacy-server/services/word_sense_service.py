"""
Service for managing word senses on structure nodes.

This service handles extraction, filtering, and updating of word sense data
from NLP analysis results, with conservative filtering to preserve existing senses.
"""

import json
from typing import List, Optional
from sqlalchemy.orm import Session

from database.models import StructureNode
from api.models.structure_nodes import WordSense
from nlp.models import NLPAnalysisResponse
from services.exceptions import ValidationError
from utils.logger import get_logger

logger = get_logger(__name__)


class WordSenseService:
    """Service for managing word senses on structure nodes."""

    def __init__(self, db: Session):
        """
        Initialize the WordSenseService.

        Args:
            db: SQLAlchemy database session for local.db
        """
        self.db = db

    def extract_word_senses(
        self, nlp_response: NLPAnalysisResponse, term: Optional[str] = None
    ) -> List[WordSense]:
        """
        Extract word senses from NLP analysis results.

        Extracts WordNet synsets from token data and converts them to WordSense instances.

        Args:
            nlp_response: NLP analysis response containing token data with structure:
                - tokens: List of TokenData objects
                - Each TokenData has: text, wordnet (with synsets list)
                - Each synset dict has: name, definition, optional domain
            term: Optional specific term to filter senses for (uses all tokens if None)

        Returns:
            List of WordSense instances extracted from the analysis
        """
        logger.debug(f"Extracting word senses from NLP analysis (term: {term})")

        word_senses = []

        # Iterate through all tokens in the analysis
        for token in nlp_response.tokens:
            # Skip if filtering by term and this token doesn't match
            if term and token.text and token.text.lower() != term.lower():
                continue

            # Extract WordNet synsets if available
            if token.wordnet and token.wordnet.synsets:
                for synset in token.wordnet.synsets:
                    try:
                        # Validate synset has required fields
                        if not isinstance(synset, dict):
                            logger.warning(f"Synset is not a dict: {synset}")
                            continue

                        synset_name = synset.get("name")
                        synset_definition = synset.get("definition")

                        if not synset_name or not synset_definition:
                            logger.warning(
                                f"Synset missing required fields (name or definition): {synset}"
                            )
                            continue

                        # Create WordSense instance
                        word_sense = WordSense(
                            term=token.text or "",
                            sense_type="wordnet",
                            sense_id=synset_name,
                            definition=synset_definition,
                            domain=synset.get("domain"),  # Optional field
                        )

                        word_senses.append(word_sense)
                        logger.debug(
                            f"Extracted word sense: term='{word_sense.term}', "
                            f"sense_id='{word_sense.sense_id}'"
                        )

                    except Exception as e:
                        logger.warning(
                            f"Failed to extract word sense from synset {synset}: {e}"
                        )
                        continue

        logger.info(f"Extracted {len(word_senses)} word senses from NLP analysis")
        return word_senses

    def update_word_senses(
        self, node_id: str, new_senses: List[WordSense], conservative: bool = True
    ) -> List[WordSense]:
        """
        Update word senses for a structure node.

        Uses conservative filtering by default: only removes senses that are no longer
        present in the new analysis, preserves existing senses that still match.

        Args:
            node_id: ID of the structure node
            new_senses: List of WordSense instances from new NLP analysis
            conservative: If True, preserves existing senses that match new analysis.
                         If False, replaces all senses with new ones.

        Returns:
            List of word senses after update

        Raises:
            ValueError: If node not found or update fails
        """
        logger.info(
            f"Updating word senses for node {node_id} with {len(new_senses)} new senses "
            f"(conservative={conservative})"
        )

        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise ValueError(f"StructureNode not found: {node_id}")

        if conservative:
            # Conservative update: preserve existing senses that still match
            existing_senses = self.get_word_senses(node_id)

            # Create set of new sense IDs for efficient lookup
            new_sense_ids = {sense.sense_id for sense in new_senses}

            # Filter existing senses: keep only those still present in new analysis
            preserved_senses = [
                sense for sense in existing_senses if sense.sense_id in new_sense_ids
            ]

            # Create set of preserved sense IDs
            preserved_sense_ids = {sense.sense_id for sense in preserved_senses}

            # Add new senses that weren't already preserved
            added_senses = [
                sense
                for sense in new_senses
                if sense.sense_id not in preserved_sense_ids
            ]

            # Combine preserved and new senses
            updated_senses = preserved_senses + added_senses

            removed_count = len(existing_senses) - len(preserved_senses)
            added_count = len(added_senses)

            logger.info(
                f"Conservative update: preserved {len(preserved_senses)}, "
                f"added {added_count}, removed {removed_count} senses"
            )

        else:
            # Non-conservative: replace all senses
            updated_senses = new_senses
            logger.info(f"Full replacement: set {len(updated_senses)} senses")

        # Serialize to JSON
        senses_json = json.dumps([sense.model_dump() for sense in updated_senses])

        # Update node (increment version after validation, before commit)
        node.word_senses = senses_json  # type: ignore

        try:
            node.version = node.version + 1  # type: ignore
            self.db.commit()
            logger.info(
                f"Successfully updated word senses for node {node_id} "
                f"(total: {len(updated_senses)})"
            )
            return updated_senses
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update word senses for node {node_id}: {e}")
            raise ValueError(f"Failed to update word senses: {e}")

    def get_word_senses(self, node_id: str) -> List[WordSense]:
        """
        Get all word senses for a structure node.

        Args:
            node_id: ID of the structure node

        Returns:
            List of WordSense instances (empty list if none)

        Raises:
            ValueError: If node not found or JSON parsing fails
        """
        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise ValueError(f"StructureNode not found: {node_id}")

        # Parse JSON field (handle null, empty string, and malformed JSON)
        if not node.word_senses:
            return []

        try:
            senses_data = json.loads(node.word_senses)  # type: ignore

            # Handle case where field is not an array
            if not isinstance(senses_data, list):
                logger.warning(
                    f"word_senses field for node {node_id} is not an array, returning empty list"
                )
                return []

            # Parse each sense into a WordSense model
            senses = []
            parse_failures = []
            for sense_dict in senses_data:
                try:
                    senses.append(WordSense(**sense_dict))
                except Exception as e:
                    logger.error(
                        f"Failed to parse word sense for node {node_id}: {e}. "
                        f"Invalid entry: {sense_dict}"
                    )
                    parse_failures.append({"data": sense_dict, "error": str(e)})

            # If any senses failed to parse, raise error - data is corrupted
            if parse_failures:
                logger.error(
                    f"CRITICAL: {len(parse_failures)} word senses for node {node_id} "
                    f"could not be parsed due to data corruption"
                )
                raise ValidationError(
                    f"Word sense data is partially corrupted: {len(parse_failures)} of "
                    f"{len(senses_data)} senses could not be loaded. Node ID: {node_id}"
                )

            return senses

        except json.JSONDecodeError as e:
            logger.error(
                f"CRITICAL: word_senses JSON for node {node_id} is corrupted and cannot be parsed: {e}. "
                f"Raw data (first 200 chars): {node.word_senses[:200] if node.word_senses else 'null'}"
            )
            raise ValidationError(
                f"Word sense data for node {node_id} is corrupted (JSON parse error). "
                f"Please contact support to recover this data."
            )

    def remove_word_senses(self, node_id: str, sense_ids: List[str]) -> List[WordSense]:
        """
        Remove specific word senses from a structure node by sense_id.

        Args:
            node_id: ID of the structure node
            sense_ids: List of sense_id values to remove

        Returns:
            List of remaining word senses after removal

        Raises:
            ValueError: If node not found or update fails
        """
        logger.info(f"Removing {len(sense_ids)} word senses from node {node_id}")

        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise ValueError(f"StructureNode not found: {node_id}")

        # Get existing senses
        existing_senses = self.get_word_senses(node_id)

        # Create set of sense IDs to remove
        remove_set = set(sense_ids)

        # Filter out senses to remove
        remaining_senses = [
            sense for sense in existing_senses if sense.sense_id not in remove_set
        ]

        removed_count = len(existing_senses) - len(remaining_senses)

        # Serialize to JSON (empty array if no senses remain)
        senses_json = json.dumps([sense.model_dump() for sense in remaining_senses])

        # Update node (increment version after validation, before commit)
        node.word_senses = senses_json  # type: ignore

        try:
            node.version = node.version + 1  # type: ignore
            self.db.commit()
            logger.info(
                f"Successfully removed {removed_count} word senses from node {node_id} "
                f"(remaining: {len(remaining_senses)})"
            )
            return remaining_senses
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to remove word senses from node {node_id}: {e}")
            raise ValueError(f"Failed to remove word senses: {e}")

    def validate_sense_identifier(self, sense_type: str, sense_id: str) -> bool:
        """
        Validate a sense identifier format.

        Currently supports basic validation for WordNet sense IDs.
        Can be extended to support other sense systems.

        Args:
            sense_type: Type of sense system (e.g., 'wordnet')
            sense_id: Sense identifier to validate

        Returns:
            True if valid

        Raises:
            ValueError: If sense identifier format is invalid
        """
        if sense_type == "wordnet":
            # WordNet synset names follow pattern: word.pos.number
            # Example: bank.n.01, run.v.03
            if not sense_id:
                raise ValueError("WordNet sense_id cannot be empty")

            parts = sense_id.split(".")
            if len(parts) != 3:
                raise ValueError(
                    f"Invalid WordNet sense_id format: '{sense_id}'. "
                    f"Expected format: word.pos.number (e.g., 'bank.n.01')"
                )

            word, pos, number = parts

            # Validate POS tag is valid WordNet POS
            valid_pos = {
                "n",
                "v",
                "a",
                "r",
                "s",
            }  # noun, verb, adjective, adverb, satellite adj
            if pos not in valid_pos:
                raise ValueError(
                    f"Invalid WordNet POS tag: '{pos}'. Must be one of {valid_pos}"
                )

            # Validate number is numeric
            if not number.isdigit():
                raise ValueError(
                    f"Invalid WordNet sense number: '{number}'. Must be numeric."
                )

            logger.debug(f"Validated WordNet sense_id: {sense_id}")
            return True

        else:
            # For other sense types, just check it's not empty
            if not sense_id:
                raise ValueError(
                    f"sense_id cannot be empty for sense_type '{sense_type}'"
                )

            logger.debug(f"Validated sense_id for {sense_type}: {sense_id}")
            return True

    def update_selected_senses(
        self, node_id: str, selected_senses: List[WordSense]
    ) -> List[WordSense]:
        """
        Update selected word senses for a structure node.

        This method uses a conservative merge strategy: it preserves existing word
        senses that are not included in the update (for different words), while
        replacing senses for words that are included in the update.

        Args:
            node_id: ID of the structure node
            selected_senses: List of WordSense instances representing user selections

        Returns:
            List of all word senses after update

        Raises:
            ValueError: If node not found, validation fails, or update fails
        """
        logger.info(
            f"Updating selected word senses for node {node_id} "
            f"with {len(selected_senses)} selections"
        )

        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise ValueError(f"StructureNode not found: {node_id}")

        # Validate all sense IDs before proceeding
        for sense in selected_senses:
            try:
                self.validate_sense_identifier(sense.sense_type, sense.sense_id)
            except ValueError as e:
                logger.error(f"Invalid sense in update: {e}")
                raise ValueError(f"Invalid sense: {e}")

        # Get existing senses with error handling for malformed JSON
        try:
            existing_senses = self.get_word_senses(node_id)
        except ValueError as e:
            logger.error(f"Failed to load existing word senses for node {node_id}: {e}")
            raise ValueError(
                f"Cannot update word senses: existing data is corrupted. {e}"
            )

        # Create set of words (terms) being updated
        updated_terms = {sense.term.lower() for sense in selected_senses}

        # Preserve existing senses for words NOT included in this update
        preserved_senses = [
            sense
            for sense in existing_senses
            if sense.term.lower() not in updated_terms
        ]

        # Combine preserved senses with new selections
        updated_senses = preserved_senses + selected_senses

        logger.info(
            f"Conservative merge: preserved {len(preserved_senses)} senses for other words, "
            f"updated {len(selected_senses)} senses"
        )

        # Serialize to JSON
        senses_json = json.dumps([sense.model_dump() for sense in updated_senses])

        # Update node (increment version after validation, before commit)
        node.word_senses = senses_json  # type: ignore

        try:
            node.version = node.version + 1  # type: ignore
            self.db.commit()
            logger.info(
                f"Successfully updated selected word senses for node {node_id} "
                f"(total: {len(updated_senses)})"
            )
            return updated_senses
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to update selected word senses for node {node_id}: {e}"
            )
            raise ValueError(f"Failed to update selected word senses: {e}")

    def get_nodes_with_word_sense(
        self, sense_id: str, limit: Optional[int] = None
    ) -> List[StructureNode]:
        """
        Find all structure nodes that have a specific word sense.

        Args:
            sense_id: Sense identifier to search for
            limit: Optional limit on number of results

        Returns:
            List of StructureNode instances that contain the given sense
        """
        logger.debug(f"Finding nodes with word sense: sense_id='{sense_id}'")

        # Query nodes using SQLite json_extract for efficiency
        # This filters at the database level instead of fetching all nodes
        from sqlalchemy import text

        query = (
            self.db.query(StructureNode)
            .filter(
                StructureNode.word_senses.isnot(None),
                StructureNode.word_senses != "",
                StructureNode.word_senses != "[]",
                text(
                    "EXISTS ("
                    "  SELECT 1 FROM json_each(word_senses) "
                    "  WHERE json_extract(value, '$.sense_id') = :sense_id"
                    ")"
                ),
            )
            .params(sense_id=sense_id)
        )

        if limit:
            query = query.limit(limit)

        matching_nodes = query.all()

        logger.debug(
            f"Found {len(matching_nodes)} nodes with word sense sense_id='{sense_id}'"
        )

        return matching_nodes

"""WordNet source implementation using NLTK"""

from typing import Optional, List
import nltk
from nltk.corpus import wordnet as wn
from .base import BaseReferenceSource
from ..models import WordNetSearchResponse, WordNetRelationsResponse, WordNetSynset, WordNetRelation
import logging

logger = logging.getLogger(__name__)

class WordNetSource(BaseReferenceSource):
    """WordNet source using NLTK"""
# mypy: ignore-errors

    def __init__(self, source_type, config):
        super().__init__(source_type, config)
        self._ensure_wordnet_data()

    def _ensure_wordnet_data(self):
        """Ensure WordNet data is downloaded"""
        try:
            # Try to access wordnet to see if it's available
            list(wn.synsets('test'))
        except LookupError:
            logger.info("Downloading WordNet data...")
            nltk.download('wordnet', quiet=True)
            nltk.download('omw-1.4', quiet=True)  # For multilingual support

    def _get_default_base_url(self) -> str:
        """WordNet doesn't use HTTP, return placeholder"""
        return "nltk://wordnet"

    def _get_proxy_domain_key(self) -> str:
        """WordNet doesn't use proxy"""
        return "wordnet"

    async def search_synsets(self, word: str, pos: Optional[str] = None, lang: str = "eng", limit: int = 20) -> WordNetSearchResponse:
        """Search for synsets of a word"""
        try:
            # Convert pos parameter to WordNet format
            wn_pos = None
            if pos:
                pos_map = {
                    "noun": wn.NOUN,
                    "verb": wn.VERB,
                    "adj": wn.ADJ,
                    "adv": wn.ADV
                }
                wn_pos = pos_map.get(pos.lower())

            # Get synsets
            synsets = wn.synsets(word, pos=wn_pos, lang=lang)[:limit]

            # Transform to response format
            synset_data = []
            for synset in synsets:
                synset_model = self._transform_synset(synset)
                synset_data.append(synset_model)

            return WordNetSearchResponse(
                **self._create_base_response(),
                word=word,
                pos=pos,
                synsets=synset_data
            )

        except Exception as e:
            logger.error(f"WordNet search failed: {e}")
            return WordNetSearchResponse(
                **self._create_base_response(success=False, error=str(e))
            )

    async def get_synset_relations(self, synset_name: str, relation_types: Optional[List[str]] = None) -> WordNetRelationsResponse:
        """Get semantic relations for a synset"""
        try:
            synset = wn.synset(synset_name)
            relations = []

            # Define available relation types
            available_relations = {
                "hypernyms": synset.hypernyms,
                "hyponyms": synset.hyponyms,
                "meronyms": synset.part_meronyms,
                "holonyms": synset.part_holonyms,
                "member_meronyms": synset.member_meronyms,
                "member_holonyms": synset.member_holonyms,
                "substance_meronyms": synset.substance_meronyms,
                "substance_holonyms": synset.substance_holonyms,
                "entailments": synset.entailments,
                "causes": synset.causes,
                "also": synset.also,
                "similar_tos": synset.similar_tos,
                "verb_groups": synset.verb_groups,
                "attributes": synset.attributes
            }

            # Filter by requested relation types
            if relation_types:
                relations_to_check = {k: v for k, v in available_relations.items() if k in relation_types}
            else:
                relations_to_check = available_relations

            # Extract relations
            for relation_type, relation_func in relations_to_check.items():
                try:
                    related_synsets = relation_func()
                    for related_synset in related_synsets:
                        relation = WordNetRelation(
                            relation_type=relation_type,
                            target_synset=self._transform_synset(related_synset)
                        )
                        relations.append(relation)
                except Exception as e:
                    logger.warning(f"Failed to get {relation_type} for {synset_name}: {e}")
                    continue

            return WordNetRelationsResponse(
                **self._create_base_response(),
                synset_id=synset_name,
                relations=relations
            )

        except Exception as e:
            logger.error(f"WordNet relations failed: {e}")
            return WordNetRelationsResponse(
                **self._create_base_response(success=False, error=str(e))
            )

    def _transform_synset(self, synset) -> WordNetSynset:
        """Transform NLTK synset to our model"""
        return WordNetSynset(
            id=synset.name(),
            name=synset.name(),
            pos=synset.pos(),
            definition=synset.definition(),
            examples=synset.examples(),
            lemmas=synset.lemma_names(),
            lexfile=synset.lexname(),
            offset=synset.offset()
        )
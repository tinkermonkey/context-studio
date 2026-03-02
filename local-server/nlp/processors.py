"""
NLP data processors for token and entity extraction.
"""
# mypy: ignore-errors

from typing import List, Any
from nlp.models import TokenData, EntityData, ConcepcyData, WordNetData, DBpediaData, NLPAnalysisResponse, TokenReference
from utils.logger import get_logger

logger = get_logger("nlp_processors")


def extract_token_data(doc, filter: bool = False) -> List[TokenData]:
    """
    Extract token-level data from spaCy doc.
    By default, filters out punctuation and stopword tokens. Set filter=False to disable filtering.
    """
    tokens = []
    doc_tokens = list(doc)
    def make_token_ref(tok):
        return TokenReference(
            index=tok.i if hasattr(tok, 'i') else None,
            text=str(tok.text) if hasattr(tok, 'text') else None,
            pos=str(tok.pos_) if hasattr(tok, 'pos_') else None,
            start_idx=tok.idx if hasattr(tok, 'idx') else None,
            end_idx=(tok.idx + len(tok.text)) if hasattr(tok, 'idx') and hasattr(tok, 'text') else None
        )

    from config import get_settings
    from nlp.models import ConcepcyRelation, ConcepcyNode
    settings = get_settings()
    relations_of_interest = [r.lower() for r in settings.concepcy_config.get("relations_of_interest", [])]

    for token in doc_tokens:
        # Filtering: skip punctuation and stopwords if filter is True
        is_punct = (hasattr(token, 'is_punct') and token.is_punct)
        is_stop = (hasattr(token, 'is_stop') and token.is_stop)
        if filter and (is_punct or is_stop):
            continue

        concepcy = None
        wordnet = None
        try:
            # Concepcy extraction
            terms_list = []
            try:
                for rel in relations_of_interest:
                    if hasattr(token._, rel):
                        rel_val = getattr(token._, rel)
                        if rel_val:
                            # rel_val can be a list or a single item
                            rel_items = rel_val if (hasattr(rel_val, '__iter__') and not isinstance(rel_val, (str, bytes, dict))) else [rel_val]
                            for item in rel_items:
                                # Try to extract subject/object/text/weight if present, else fallback
                                try:
                                    # If item is already a dict with keys, try to extract fields
                                    if isinstance(item, dict):
                                        subject = item.get('start')
                                        object_ = item.get('end')
                                        relation = item.get('relation', rel)
                                        text = item.get('text')
                                        weight = item.get('weight')

                                        # If subject/object are dicts, convert to ConcepcyNode
                                        if isinstance(subject, dict):
                                            subject = ConcepcyNode(**subject)
                                        if isinstance(object_, dict):
                                            object_ = ConcepcyNode(**object_)
                                        terms_list.append(ConcepcyRelation(
                                            subject=subject,
                                            object=object_,
                                            relation=relation,
                                            text=text,
                                            weight=weight
                                        ))
                                    else:
                                        logger.warning(f"Unexpected item type for Concepcy relation '{rel}' on token '{token.text}': {type(item)}")
                                except Exception as rel_e:
                                    logger.debug(f"Failed to build ConcepcyRelation for '{token.text}' relation '{rel}': {rel_e}")
                if len(terms_list):
                    concepcy = ConcepcyData(
                        related_terms=terms_list,
                    )
            except Exception as ce:
                logger.warning(f"Concepcy extraction failed for '{token.text}': {ce}")

            # WordNet extraction
            try:
                if hasattr(token._, "wordnet") and token._.wordnet:
                    wn = token._.wordnet
                    synsets = []
                    lemmas = []
                    definitions = []
                    try:
                        synset_iter = wn.synsets()
                        if hasattr(synset_iter, '__iter__'):
                            for s in synset_iter:
                                try:
                                    synset_data = {
                                        "name": str(s.name()) if hasattr(s, 'name') else "",
                                        "definition": str(s.definition()) if hasattr(s, 'definition') else "",
                                        "lemmas": [str(lemma.name()) for lemma in s.lemmas()] if hasattr(s, 'lemmas') else [],
                                        "pos": str(s.pos()) if hasattr(s, 'pos') else "",
                                        "offset": int(s.offset()) if hasattr(s, 'offset') else 0,
                                        "domain": str(s.lexname()) if hasattr(s, 'lexname') else ""
                                    }
                                    synsets.append(synset_data)
                                    definitions.append(synset_data["definition"])
                                except Exception as synset_e:
                                    logger.debug(f"Failed to process synset for '{token.text}': {synset_e}")
                    except Exception as synsets_e:
                        logger.debug(f"Failed to get synsets for '{token.text}': {synsets_e}")
                    try:
                        lemma_iter = wn.lemmas()
                        if hasattr(lemma_iter, '__iter__'):
                            for lemma in lemma_iter:
                                try:
                                    lemma_data = {
                                        "name": str(lemma.name()) if hasattr(lemma, 'name') else "",
                                        "synset": str(lemma.synset().name()) if hasattr(lemma, 'synset') and hasattr(lemma.synset(), 'name') else "",
                                        "count": int(lemma.count()) if hasattr(lemma, 'count') and lemma.count() is not None else 0
                                    }
                                    lemmas.append(lemma_data)
                                except Exception as lemma_e:
                                    logger.debug(f"Failed to process lemma for '{token.text}': {lemma_e}")
                    except Exception as lemmas_e:
                        logger.debug(f"Failed to get lemmas for '{token.text}': {lemmas_e}")
                    wordnet = WordNetData(
                        synsets=synsets,
                        lemmas=lemmas,
                        definitions=[str(d) for d in definitions]  # type: ignore
                    )
            except Exception as we:
                logger.warning(f"WordNet extraction failed for '{token.text}': {we}")

            # TokenData construction
            try:
                text_val = str(token.text) if hasattr(token, 'text') else ""
                lemma_val = str(token.lemma_) if hasattr(token, 'lemma_') and token.lemma_ else None
                pos_val = str(token.pos_) if hasattr(token, 'pos_') and token.pos_ else None
                dep_val = str(token.dep_) if hasattr(token, 'dep_') and token.dep_ else None
                tag_val = str(token.tag_) if hasattr(token, 'tag_') and token.tag_ else None
                start_idx_val = token.idx if hasattr(token, 'idx') else None
                end_idx_val = (token.idx + len(token.text)) if hasattr(token, 'idx') and hasattr(token, 'text') else None

                head_ref = None
                if hasattr(token, 'head') and token.head is not token:
                    head_ref = make_token_ref(token.head)

                children_refs = []
                if hasattr(token, 'children'):
                    try:
                        children_refs = [make_token_ref(child) for child in token.children]
                    except Exception as e:
                        logger.debug(f"Failed to extract children for '{token.text}': {e}")

                ancestors_refs = []
                if hasattr(token, 'ancestors'):
                    try:
                        ancestors_refs = [make_token_ref(ancestor) for ancestor in token.ancestors]
                    except Exception as e:
                        logger.debug(f"Failed to extract ancestors for '{token.text}': {e}")

                subtree_refs = []
                if hasattr(token, 'subtree'):
                    try:
                        subtree_refs = [make_token_ref(subtok) for subtok in token.subtree]
                    except Exception as e:
                        logger.debug(f"Failed to extract subtree for '{token.text}': {e}")

                is_alpha_val = bool(token.is_alpha) if hasattr(token, 'is_alpha') else None
                is_stop_val = bool(token.is_stop) if hasattr(token, 'is_stop') else None
                is_oov_val = bool(token.is_oov) if hasattr(token, 'is_oov') else None
                like_url_val = bool(token.like_url) if hasattr(token, 'like_url') else None
                is_digit_val = bool(token.is_digit) if hasattr(token, 'is_digit') else None
                ent_iob_val = str(token.ent_iob_) if hasattr(token, 'ent_iob_') and token.ent_iob_ else None
                ent_type_val = str(token.ent_type_) if hasattr(token, 'ent_type_') and token.ent_type_ else None
                ent_kb_id_val = str(token.ent_kb_id_) if hasattr(token, 'ent_kb_id_') and token.ent_kb_id_ else None
                ent_id_val = int(token.ent_id) if hasattr(token, 'ent_id') and token.ent_id is not None else None
                sentiment_val = float(token.sentiment) if hasattr(token, 'sentiment') and token.sentiment is not None else None

                tokens.append(TokenData(
                    text=text_val,
                    lemma=lemma_val,
                    pos=pos_val,
                    dep=dep_val,
                    tag=tag_val,
                    start_idx=start_idx_val,
                    end_idx=end_idx_val,
                    head=head_ref,
                    children=children_refs,
                    ancestors=ancestors_refs,
                    subtree=subtree_refs,
                    is_alpha=is_alpha_val,
                    is_stop=is_stop_val,
                    is_oov=is_oov_val,
                    like_url=like_url_val,
                    is_digit=is_digit_val,
                    ent_iob=ent_iob_val,
                    ent_type=ent_type_val,
                    ent_kb_id=ent_kb_id_val,
                    ent_id=ent_id_val,
                    sentiment=sentiment_val,
                    concepcy=concepcy,
                    wordnet=wordnet,
                ))
            except Exception as te:
                logger.warning(f"TokenData construction failed for '{token.text}': {te}")
                try:
                    tokens.append(TokenData(text=str(token.text) if hasattr(token, 'text') else ""))  # type: ignore
                except Exception as backup_e:
                    logger.error(f"Even backup TokenData construction failed: {backup_e}")
                    tokens.append(TokenData(text=""))  # type: ignore
        except Exception as e:
            logger.warning(f"General token extraction failed for token: {e}")
            try:
                tokens.append(TokenData(text=str(token.text) if hasattr(token, 'text') else ""))  # type: ignore
            except Exception:
                tokens.append(TokenData(text=""))  # type: ignore
    return tokens


def extract_entity_data(doc) -> List[EntityData]:
    """
    Extract entity-level NLP data from spaCy doc.
    Handles DBpedia extraction, with error handling.
    """
    entities = []
    for ent in doc.ents:
        try:
            dbpedia = None
            kb_id = getattr(ent, "kb_id_", None)
            raw_result = getattr(ent._, "dbpedia_raw_result", None) if hasattr(ent._, "dbpedia_raw_result") else None
            similarity = getattr(ent._, "dbpedia_similarity", None) if hasattr(ent._, "dbpedia_similarity") else None
            uri = getattr(ent._, "dbpedia_uri", None) if hasattr(ent._, "dbpedia_uri") else None
            label = getattr(ent._, "dbpedia_label", None) if hasattr(ent._, "dbpedia_label") else None
            if uri or label or similarity or raw_result:
                dbpedia = DBpediaData(
                    uri=uri,
                    label=label,
                    similarity=similarity,
                    raw_result=raw_result
                )
            entities.append(EntityData(
                text=ent.text,
                label=getattr(ent, "label_", None),
                kb_id=kb_id,
                dbpedia=dbpedia
            ))
        except Exception as e:
            logger.warning(f"Entity extraction failed for '{ent.text}': {e}")
            entities.append(EntityData(text=ent.text))
    return entities


def process_nlp_result(text: str, doc: Any) -> NLPAnalysisResponse:
    """
    Process spaCy doc and return structured NLPAnalysisResponse.
    Combines token and entity data.
    """
    tokens = extract_token_data(doc)
    entities = extract_entity_data(doc)
    return NLPAnalysisResponse(
        text=text,
        tokens=tokens,
        entities=entities
    )

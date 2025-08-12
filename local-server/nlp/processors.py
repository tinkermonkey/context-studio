"""
NLP data processors for token and entity extraction.
"""

from typing import List, Any
from nlp.models import TokenData, EntityData, ConcepcyData, WordNetData, DBpediaData, Sense2VecData, NLPAnalysisResponse
from utils.logger import get_logger

logger = get_logger("nlp_processors")


def extract_token_data(doc) -> List[TokenData]:
    """
    Extract token-level data from spaCy doc.
    """
    tokens = []

    for token in doc:
        concepcy = None
        wordnet = None
        try:
            # Concepcy extraction
            try:
                if hasattr(token._, "relatedto") and token._.relatedto:
                    related_terms = token._.relatedto
                    # Ensure related_terms is iterable and convert to list of strings
                    if related_terms is not None:
                        if hasattr(related_terms, '__iter__') and not isinstance(related_terms, (str, bytes)):
                            terms_list = [str(t) for t in related_terms]
                        else:
                            terms_list = [str(related_terms)]
                        
                        score_val = None
                        if hasattr(token._, "concepcy_score") and token._.concepcy_score is not None:
                            score_val = float(token._.concepcy_score)
                        
                        concepcy = ConcepcyData(
                            related_terms=terms_list,
                            score=score_val
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
                    
                    # Safely extract synsets
                    try:
                        synset_iter = wn.synsets()
                        if hasattr(synset_iter, '__iter__'):
                            for s in synset_iter:
                                try:
                                    synset_data = {
                                        "name": str(s.name()) if hasattr(s, 'name') else "",
                                        "definition": str(s.definition()) if hasattr(s, 'definition') else "",
                                        "lemmas": [str(l.name()) for l in s.lemmas()] if hasattr(s, 'lemmas') else [],
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
                    
                    # Safely extract lemmas
                    try:
                        lemma_iter = wn.lemmas()
                        if hasattr(lemma_iter, '__iter__'):
                            for l in lemma_iter:
                                try:
                                    lemma_data = {
                                        "name": str(l.name()) if hasattr(l, 'name') else "",
                                        "synset": str(l.synset().name()) if hasattr(l, 'synset') and hasattr(l.synset(), 'name') else "",
                                        "count": int(l.count()) if hasattr(l, 'count') and l.count() is not None else 0
                                    }
                                    lemmas.append(lemma_data)
                                except Exception as lemma_e:
                                    logger.debug(f"Failed to process lemma for '{token.text}': {lemma_e}")
                    except Exception as lemmas_e:
                        logger.debug(f"Failed to get lemmas for '{token.text}': {lemmas_e}")
                    
                    # Always create WordNetData object if WordNet extension is available
                    wordnet = WordNetData(
                        synsets=synsets,
                        lemmas=lemmas,
                        definitions=definitions
                    )
            except Exception as we:
                logger.warning(f"WordNet extraction failed for '{token.text}': {we}")
            
            # Extract Sense2Vec data
            sense2vec_data = Sense2VecData()
            if hasattr(token._, 'in_s2v'):
                try:
                    sense2vec_data.in_s2v = bool(token._.in_s2v) if hasattr(token._, 'in_s2v') else False
                    sense2vec_data.key = str(token._.s2v_key) if hasattr(token._, 's2v_key') and token._.s2v_key else None
                    sense2vec_data.freq = int(token._.s2v_freq) if hasattr(token._, 's2v_freq') and token._.s2v_freq is not None else None
                    sense2vec_data.other_senses = list(token._.s2v_other_senses) if hasattr(token._, 's2v_other_senses') and token._.s2v_other_senses else []
                    sense2vec_data.most_similar = []
                    
                    if hasattr(token._, 's2v_most_similar'):
                        most_similar = token._.s2v_most_similar(5)
                        if isinstance(most_similar, list) and len(most_similar) > 0:
                            for similar in most_similar:
                                try:
                                    # Handle the tuple structure: ((word, sense), score)
                                    if isinstance(similar, tuple) and len(similar) == 2:
                                        word_sense_tuple, score = similar
                                        if isinstance(word_sense_tuple, tuple) and len(word_sense_tuple) == 2:
                                            word, sense = word_sense_tuple
                                            # Convert numpy.float32 to regular float
                                            score_val = float(score) if score is not None else 0.0
                                            sense2vec_data.most_similar.append({
                                                "word": str(word), 
                                                "sense": str(sense), 
                                                "score": score_val
                                            })
                                except Exception as sim_e:
                                    logger.warning(f"Failed to process similar term {similar} for '{token.text}': {sim_e}")
                        else:
                            logger.debug(f"s2v found nothing similar for: {sense2vec_data.key}")
                except Exception as s2v_e:
                    logger.debug(f"Sense2Vec extraction failed for '{token.text}': {s2v_e}")
                    # Reset to default values on error
                    sense2vec_data = Sense2VecData()
            # TokenData construction
            try:
                # Safely extract token attributes
                text_val = str(token.text) if hasattr(token, 'text') else ""
                lemma_val = str(token.lemma_) if hasattr(token, 'lemma_') and token.lemma_ else None
                pos_val = str(token.pos_) if hasattr(token, 'pos_') and token.pos_ else None
                
                tokens.append(TokenData(
                    text=text_val,
                    lemma=lemma_val,
                    pos=pos_val,
                    concepcy=concepcy,
                    wordnet=wordnet,
                    sense2vec=sense2vec_data,
                ))
            except Exception as te:
                logger.warning(f"TokenData construction failed for '{token.text}': {te}")
                # Create minimal token data on error
                try:
                    tokens.append(TokenData(text=str(token.text) if hasattr(token, 'text') else ""))
                except Exception as backup_e:
                    logger.error(f"Even backup TokenData construction failed: {backup_e}")
                    tokens.append(TokenData(text=""))
        except Exception as e:
            logger.warning(f"General token extraction failed for token: {e}")
            try:
                tokens.append(TokenData(text=str(token.text) if hasattr(token, 'text') else ""))
            except:
                tokens.append(TokenData(text=""))
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

import os
import threading
from typing import Optional
import spacy
import concepcy
import spacy_dbpedia_spotlight
from spacy_wordnet.wordnet_annotator import WordnetAnnotator

s2v_config = {
    "local_path": "./downloads/s2v_reddit_2015_md"
}
s2v_config["abs_path"] = os.path.abspath(s2v_config["local_path"]) 

class NLPPipeline:
    """
    NLP pipeline manager for spaCy and custom components.
    Handles initialization, error handling, and component loading.
    """
    def __init__(self, model_name: str = "en_core_web_sm"):
        self.model_name = model_name
        self.nlp = None
        self.s2v = None
        self._initialized = False
        self._error = None
        self._lock = threading.Lock()
        self._init_pipeline()

    def _init_pipeline(self):
        """
        Initialize spaCy pipeline and add components in correct order.
        """
        import logging
        logger = logging.getLogger("nlp_pipeline")
        try:
            self.nlp = spacy.load(self.model_name)
        except Exception as e:
            self._error = f"spaCy model loading failed: {e}"
            logger.error(self._error)
            return

        # Add custom components
        try:
            self.nlp.add_pipe("concepcy")
        except Exception as e:
            self._error = f"Failed to add concepcy: {e}"
            logger.error(self._error)
            return
        
        try:
            self.nlp.add_pipe("dbpedia_spotlight")
        except Exception as e:
            self._error = f"Failed to add dbpedia_spotlight: {e}"
            logger.error(self._error)
            return
        
        try:
            self.nlp.add_pipe("spacy_wordnet", after="tagger")
        except Exception as e:
            self._error = f"Failed to add spacy_wordnet: {e}"
            logger.error(self._error)
            return
        
        try:
            self.s2v = self.nlp.add_pipe("sense2vec")
            # Load the S2V dataset
            print(f"Loading sense2vec model from {s2v_config['abs_path']}...")
            self.s2v.from_disk(s2v_config["abs_path"])
        except Exception as e:
            self._error = f"Failed to add sense2vec: {e}"
            logger.error(self._error)
            return
        
        self._initialized = True

    def process(self, text: str):
        """Process text through the spaCy pipeline"""
        if not self.nlp:
            raise RuntimeError("Pipeline not initialized")

        return self.nlp(text)

    def get_nlp(self) -> Optional[spacy.language.Language]:
        """
        Return the spaCy nlp object if initialized, else None.
        """
        return self.nlp if self._initialized else None

    def get_error(self) -> Optional[str]:
        """
        Return error message if initialization failed.
        """
        return self._error

_pipeline_instance: Optional[NLPPipeline] = None
_pipeline_lock = threading.Lock()

def get_pipeline() -> NLPPipeline:
    """
    Get the global NLPPipeline instance (singleton, thread-safe).
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        with _pipeline_lock:
            if _pipeline_instance is None:
                _pipeline_instance = NLPPipeline()
    return _pipeline_instance

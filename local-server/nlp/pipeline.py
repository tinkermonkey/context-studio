import threading
import spacy
import concepcy
import spacy_dbpedia_spotlight
from typing import Optional
from spacy_wordnet.wordnet_annotator import WordnetAnnotator
from config import get_settings
from utils.logger import get_logger
from nlp.proxy_manager import get_proxy_manager

logger = get_logger(__name__)

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
        self.proxy_manager = get_proxy_manager()
        self._init_pipeline()

    def _init_pipeline(self):
        """
        Initialize spaCy pipeline and add components in correct order.
        """
        logger.info(f"Initializing NLP pipeline with model: {self.model_name}")
        
        # Start proxy if any reference APIs are enabled
        if self.proxy_manager.is_proxy_enabled():
            if not self.proxy_manager.start_proxy():
                self._error = "Failed to start reference API caching proxy"
                logger.error(self._error)
                return
        
        try:
            logger.info("Loading spaCy model...")
            self.nlp = spacy.load(self.model_name)
            logger.info("spaCy model loaded successfully")
        except Exception as e:
            self._error = f"spaCy model loading failed: {e}"
            logger.error(self._error)
            return

        # Add custom components with proxy support
        self._add_concepcy_component()
        self._add_dbpedia_spotlight_component()
        self._add_spacy_wordnet_component()
        self._add_sense2vec_component()
        
        self._initialized = True
        logger.info("NLP pipeline initialization completed successfully")

    def _add_concepcy_component(self):
        """Add concepcy component with optional proxy configuration"""
        try:
            settings = get_settings()
            logger.info("Adding concepcy component...")
            use_proxy = settings.ENABLE_CACHING_PROXY.get("concepcy", False)
            config = settings.get_concepcy_config(use_proxy=use_proxy)
            
            self.nlp.add_pipe("concepcy", config=config)
            logger.info(f"concepcy component added successfully (proxy: {use_proxy})")
        except Exception as e:
            self._error = f"Failed to add concepcy: {e}"
            logger.error(self._error)
            raise

    def _add_dbpedia_spotlight_component(self):
        """Add DBpedia Spotlight component with optional proxy configuration"""
        try:
            settings = get_settings()
            logger.info("Adding dbpedia_spotlight component...")
            use_proxy = settings.ENABLE_CACHING_PROXY.get("spacy_dbpedia_spotlight", False)
            
            if use_proxy:
                proxy_config = settings.REFERENCE_API_BUDDY_CONFIG
                host = proxy_config["server"]["host"]
                port = proxy_config["server"]["port"]
                endpoint = f"http://{host}:{port}/dbpedia_spotlight"
                
                self.nlp.add_pipe("dbpedia_spotlight", config={
                    "dbpedia_rest_endpoint": endpoint
                })
                logger.info(f"dbpedia_spotlight component added with proxy: {endpoint}")
            else:
                self.nlp.add_pipe("dbpedia_spotlight")
                logger.info("dbpedia_spotlight component added (direct)")
                
        except Exception as e:
            self._error = f"Failed to add dbpedia_spotlight: {e}"
            logger.error(self._error)
            raise

    def _add_spacy_wordnet_component(self):
        """Add spacy_wordnet component"""
        try:
            logger.info("Adding spacy_wordnet component...")
            self.nlp.add_pipe("spacy_wordnet", after="tagger")
            logger.info("spacy_wordnet component added successfully")
        except Exception as e:
            self._error = f"Failed to add spacy_wordnet: {e}"
            logger.error(self._error)
            raise

    def _add_sense2vec_component(self):
        """Add sense2vec component"""
        try:
            settings = get_settings()
            logger.info("Adding sense2vec component...")
            self.s2v = self.nlp.add_pipe("sense2vec")
            # Load the S2V dataset
            logger.info(f"Loading sense2vec model from {settings.s2v_config['abs_path']}...")
            self.s2v.from_disk(settings.s2v_config["abs_path"])
            logger.info("sense2vec component loaded successfully")
        except Exception as e:
            self._error = f"Failed to add sense2vec: {e}"
            logger.error(self._error)
            raise

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

    def is_initialized(self) -> bool:
        """
        Check if the pipeline is fully initialized and ready to use.
        """
        return self._initialized and self.nlp is not None

    def get_status(self) -> dict:
        """
        Get the current status of the pipeline for debugging/monitoring.
        """
        return {
            "initialized": self._initialized,
            "model_name": self.model_name,
            "has_nlp": self.nlp is not None,
            "has_s2v": self.s2v is not None,
            "error": self._error
        }

    def reload_pipeline(self):
        """Reload the pipeline with updated configuration"""
        logger.info("Reloading NLP pipeline...")
        
        # Stop current pipeline
        self._initialized = False
        self.nlp = None
        self.s2v = None
        self._error = None
        
        # Restart proxy with new configuration
        if self.proxy_manager.is_proxy_enabled():
            if not self.proxy_manager.restart_proxy():
                self._error = "Failed to restart reference API caching proxy"
                logger.error(self._error)
                return False
        else:
            self.proxy_manager.stop_proxy()
        
        # Reinitialize pipeline
        self._init_pipeline()
        return self._initialized

    def shutdown(self):
        """Shutdown the pipeline and clean up resources"""
        logger.info("Shutting down NLP pipeline...")
        self._initialized = False
        self.nlp = None
        self.s2v = None
        
        # Stop the proxy
        self.proxy_manager.stop_proxy()

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

import threading
import spacy
import spacy.tokens
import concepcy
import spacy_dbpedia_spotlight
from typing import Optional
from spacy_wordnet.wordnet_annotator import WordnetAnnotator
from config import get_settings, get_config_manager
from utils.logger import get_logger
from nlp.proxy_manager import get_proxy_manager

logger = get_logger(__name__)

class NLPPipeline:
    """
    NLP pipeline manager for spaCy and custom components.
    Handles initialization, error handling, and component loading.
    """
    def __init__(self, model_name: str = "en_core_web_lg"):
        self.model_name = model_name
        self.nlp = None
        self.s2v = None
        self._initialized = False
        self._error = None
        self._lock = threading.Lock()
        self.proxy_manager = get_proxy_manager()
        self.config_manager = get_config_manager()
        self.settings = self.config_manager.settings
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
        """Add concepcy component using centralized reference source config"""
        conceptnet_config = self.settings.reference_sources.conceptnet
        
        if not conceptnet_config.enabled:
            logger.info("ConceptNet disabled, skipping concepcy component")
            return
            
        try:
            logger.info("Adding concepcy component...")
            
            # Build concepcy config from reference source settings
            concepcy_config = {
                "relations_of_interest": self.settings.nlp.concepcy_relations,
                "filter_missing_text": self.settings.nlp.filter_missing_text,
                "filter_edge_weight": self.settings.nlp.edge_weight_filter
            }
            
            # Add proxy URL if proxy is enabled for this source
            if conceptnet_config.use_proxy and self.settings.proxy_server.enabled:
                proxy_host = self.settings.proxy_server.host
                proxy_port = self.settings.proxy_server.port
                concepcy_config["url"] = f"http://{proxy_host}:{proxy_port}/conceptnet/query?node=/c/{{lang}}/{{word}}&other=/c/{{lang}}"
            
            self.nlp.add_pipe("concepcy", config=concepcy_config)
            logger.info(f"concepcy component added (proxy: {conceptnet_config.use_proxy})")
            
        except Exception as e:
            logger.error(f"Failed to add concepcy: {e}")
            raise

    def _add_dbpedia_spotlight_component(self):
        """Add DBpedia Spotlight component using centralized reference source config"""
        dbpedia_spotlight_config = self.settings.reference_sources.dbpedia_spotlight
        
        if not dbpedia_spotlight_config.enabled:
            logger.info("DBpedia Spotlight disabled, skipping component")
            return
            
        try:
            logger.info("Adding dbpedia_spotlight component...")
            
            component_config = {}
            
            # Add proxy endpoint if proxy is enabled for this source
            if dbpedia_spotlight_config.use_proxy and self.settings.proxy_server.enabled:
                proxy_host = self.settings.proxy_server.host
                proxy_port = self.settings.proxy_server.port
                component_config["dbpedia_rest_endpoint"] = f"http://{proxy_host}:{proxy_port}/dbpedia_spotlight"
            else:
                component_config["dbpedia_rest_endpoint"] = dbpedia_spotlight_config.upstream_url
                
            self.nlp.add_pipe("dbpedia_spotlight", config=component_config)
            logger.info(f"dbpedia_spotlight component added (proxy: {dbpedia_spotlight_config.use_proxy})")
            
        except Exception as e:
            logger.error(f"Failed to add dbpedia_spotlight: {e}")
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
            
            # Check if the _s2v extension already exists
            if spacy.tokens.Doc.has_extension("_s2v"):
                logger.debug("_s2v extension already exists, removing it before adding sense2vec component")
                # Remove the existing extension
                spacy.tokens.Doc.remove_extension("_s2v")
            
            self.s2v = self.nlp.add_pipe("sense2vec")
            # Load the S2V dataset
            logger.info(f"Loading sense2vec model from {settings.nlp.sense2vec_path}...")
            self.s2v.from_disk(settings.nlp.sense2vec_path)
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


def invalidate_pipeline():
    """Invalidate the current pipeline instance to force reinitialization"""
    global _pipeline_instance
    with _pipeline_lock:
        if _pipeline_instance:
            logger.info("Invalidating NLP pipeline due to configuration change")
            try:
                _pipeline_instance.cleanup()
            except Exception as e:
                logger.warning(f"Error during pipeline cleanup: {e}")
            _pipeline_instance = None


def get_pipeline() -> NLPPipeline:
    """
    Get the global NLPPipeline instance (singleton, thread-safe).
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        with _pipeline_lock:
            if _pipeline_instance is None:
                settings = get_settings()
                _pipeline_instance = NLPPipeline(model_name=settings.nlp.model_name)
    return _pipeline_instance

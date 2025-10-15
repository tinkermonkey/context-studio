import threading
import spacy
import spacy.tokens
import concepcy
import spacy_dbpedia_spotlight
from spacy_wordnet.wordnet_annotator import WordnetAnnotator
from typing import Optional
from config import get_settings, get_config_manager
from utils.logger import get_logger
from nlp.proxy_manager import get_proxy_manager
from nlp.model_downloader import get_model_downloader

logger = get_logger(__name__)

## DO NOT REMOVE THESE - needed to register custom pipeline components
_concepcy = concepcy
_dbpedia_spotlight = spacy_dbpedia_spotlight
_spacy_wordnet = WordnetAnnotator
## DO NOT REMOVE THESE - needed to register custom pipeline components

class NLPPipeline:
    """
    NLP pipeline manager for spaCy and custom components.
    Handles initialization, error handling, and component loading.
    """
    def __init__(self, model_name: str = "en_core_web_lg"):
        self.model_name = model_name
        self.nlp = None
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
        
        # Ensure spaCy model is available (download if necessary)
        model_downloader = get_model_downloader()
        success, error = model_downloader.ensure_spacy_model(
            self.model_name,
            auto_download=self.settings.nlp.auto_download_models,
            timeout=self.settings.nlp.download_timeout
        )
        if not success:
            self._error = f"spaCy model {self.model_name} unavailable: {error}"
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
        
        self._initialized = True
        logger.info("NLP pipeline initialization completed successfully")

    def _add_concepcy_component(self):
        """Add concepcy component using centralized reference source config"""
        if concepcy is None:
            logger.info("concepcy library not available, skipping concepcy component")
            return

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
            
            # Add proxy URL if proxy is enabled for this source AND proxy manager says proxy is enabled
            if conceptnet_config.use_proxy and self.settings.proxy_server.enabled and self.proxy_manager.is_proxy_enabled():
                proxy_host = self.settings.proxy_server.host
                proxy_port = self.settings.proxy_server.port
                concepcy_config["url"] = f"http://{proxy_host}:{proxy_port}/conceptnet/query?node=/c/{{lang}}/{{word}}&other=/c/{{lang}}"
                logger.info(f"concepcy will use proxy at {proxy_host}:{proxy_port}")
            else:
                logger.info("concepcy will use default ConceptNet API directly")
            
            self.nlp.add_pipe("concepcy", config=concepcy_config)
            logger.info(f"concepcy component added (proxy: {conceptnet_config.use_proxy and self.proxy_manager.is_proxy_enabled()})")
            
        except Exception as e:
            logger.error(f"Failed to add concepcy: {e}")
            raise

    def _add_dbpedia_spotlight_component(self):
        """Add DBpedia Spotlight component using centralized reference source config"""
        if spacy_dbpedia_spotlight is None:
            logger.info("spacy_dbpedia_spotlight library not available, skipping component")
            return

        dbpedia_spotlight_config = self.settings.reference_sources.dbpedia_spotlight

        if not dbpedia_spotlight_config.enabled:
            logger.info("DBpedia Spotlight disabled, skipping component")
            return

        try:
            logger.info("Adding dbpedia_spotlight component...")
            
            component_config = {}
            
            # Add proxy endpoint if proxy is enabled for this source AND proxy manager says proxy is enabled
            if dbpedia_spotlight_config.use_proxy and self.settings.proxy_server.enabled and self.proxy_manager.is_proxy_enabled():
                proxy_host = self.settings.proxy_server.host
                proxy_port = self.settings.proxy_server.port
                component_config["dbpedia_rest_endpoint"] = f"http://{proxy_host}:{proxy_port}/dbpedia_spotlight"
                logger.info(f"dbpedia_spotlight will use proxy at {proxy_host}:{proxy_port}")
            else:
                component_config["dbpedia_rest_endpoint"] = dbpedia_spotlight_config.upstream_url
                logger.info("dbpedia_spotlight will use upstream API directly")
                
            self.nlp.add_pipe("dbpedia_spotlight", config=component_config)
            logger.info(f"dbpedia_spotlight component added (proxy: {dbpedia_spotlight_config.use_proxy and self.proxy_manager.is_proxy_enabled()})")
            
        except Exception as e:
            logger.error(f"Failed to add dbpedia_spotlight: {e}")
            raise

    def _add_spacy_wordnet_component(self):
        """Add spacy_wordnet component"""
        if WordnetAnnotator is None:
            logger.info("spacy_wordnet library not available, skipping component")
            return

        try:
            # Ensure NLTK wordnet data is available
            self._ensure_wordnet_data()

            logger.info("Adding spacy_wordnet component...")
            self.nlp.add_pipe("spacy_wordnet", after="tagger")
            logger.info("spacy_wordnet component added successfully")
        except Exception as e:
            self._error = f"Failed to add spacy_wordnet: {e}"
            logger.error(self._error)
            raise

    def _ensure_wordnet_data(self):
        """Ensure NLTK WordNet data is downloaded"""
        try:
            import nltk
            from nltk.corpus import wordnet as wn
            # Try to access wordnet to see if it's available
            list(wn.synsets('test'))
        except LookupError:
            logger.info("Downloading NLTK WordNet data...")
            import nltk
            nltk.download('wordnet', quiet=True)
            nltk.download('omw-1.4', quiet=True)  # For multilingual support
            logger.info("NLTK WordNet data downloaded successfully")

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
            "error": self._error
        }

    def reload_pipeline(self):
        """Reload the pipeline with updated configuration"""
        logger.info("Reloading NLP pipeline...")
        
        # Stop current pipeline
        self._initialized = False
        self.nlp = None
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
                _pipeline_instance.shutdown()
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

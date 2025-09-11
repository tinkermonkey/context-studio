"""
Unit tests for NLP Pipeline proxy integration.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch
from nlp.pipeline import NLPPipeline


class TestPipelineProxyIntegration:
    """Test cases for NLP Pipeline proxy integration"""

    def setup_method(self):
        """Setup for each test method"""
        # Reset the global pipeline instance
        import nlp.pipeline

        nlp.pipeline._pipeline_instance = None

    @patch("nlp.pipeline.get_settings")
    @patch("nlp.pipeline.get_proxy_manager")
    @patch("nlp.pipeline.spacy.load")
    def test_pipeline_init_with_proxy_disabled(
        self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings
    ):
        """Test pipeline initialization when proxy is disabled"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False,
        }
        mock_settings.s2v_config = {"abs_path": "/test/path"}
        mock_get_settings.return_value = mock_settings

        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.is_proxy_enabled.return_value = False
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # Mock spaCy
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        pipeline = NLPPipeline()

        # Verify proxy was not started
        mock_proxy_manager.start_proxy.assert_not_called()
        assert pipeline.proxy_manager is mock_proxy_manager

    @patch("nlp.pipeline.get_settings")
    @patch("nlp.pipeline.get_proxy_manager")
    @patch("nlp.pipeline.spacy.load")
    def test_pipeline_init_with_proxy_enabled(
        self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings
    ):
        """Test pipeline initialization when proxy is enabled"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": True,
            "spacy_dbpedia_spotlight": False,
        }
        mock_settings.s2v_config = {"abs_path": "/test/path"}
        mock_settings.get_concepcy_config.return_value = {"test": "config"}
        mock_get_settings.return_value = mock_settings

        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.is_proxy_enabled.return_value = True
        mock_proxy_manager.start_proxy.return_value = True
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # Mock spaCy
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        pipeline = NLPPipeline()

        # Verify proxy was started
        mock_proxy_manager.start_proxy.assert_called_once()

    @patch("nlp.pipeline.get_settings")
    @patch("nlp.pipeline.get_proxy_manager")
    def test_pipeline_init_proxy_start_failure(
        self, mock_get_proxy_manager, mock_get_settings
    ):
        """Test pipeline initialization when proxy fails to start"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": True,
            "spacy_dbpedia_spotlight": False,
        }
        mock_get_settings.return_value = mock_settings

        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.is_proxy_enabled.return_value = True
        mock_proxy_manager.start_proxy.return_value = False
        mock_get_proxy_manager.return_value = mock_proxy_manager

        pipeline = NLPPipeline()

        # Verify pipeline failed to initialize
        assert not pipeline._initialized
        assert "Failed to start reference API caching proxy" in pipeline._error

    @patch("nlp.pipeline.get_settings")
    @patch("nlp.pipeline.get_config_manager")
    @patch("nlp.pipeline.get_proxy_manager")
    @patch("nlp.pipeline.spacy.load")
    def test_add_concepcy_component_with_proxy(
        self,
        mock_spacy_load,
        mock_get_proxy_manager,
        mock_get_config_manager,
        mock_get_settings,
    ):
        """Test adding concepcy component with proxy enabled"""
        # Mock config manager and settings
        mock_config_manager = Mock()
        mock_settings = Mock()

        # Mock reference sources config for conceptnet
        mock_conceptnet_config = Mock()
        mock_conceptnet_config.enabled = True
        mock_conceptnet_config.use_proxy = True

        # Mock proxy server config
        mock_proxy_server_config = Mock()
        mock_proxy_server_config.enabled = True
        mock_proxy_server_config.host = "127.0.0.1"
        mock_proxy_server_config.port = 18080

        # Mock NLP config
        mock_nlp_config = Mock()
        mock_nlp_config.concepcy_relations = ["RELATED_TO", "IS_A", "PART_OF"]
        mock_nlp_config.filter_missing_text = True
        mock_nlp_config.edge_weight_filter = 2.0
        mock_nlp_config.sense2vec_path = "/test/path"

        # Mock reference sources
        mock_reference_sources = Mock()
        mock_reference_sources.conceptnet = mock_conceptnet_config
        mock_reference_sources.dbpedia_spotlight = Mock()
        mock_reference_sources.dbpedia_spotlight.enabled = False

        # Setup settings mock
        mock_settings.reference_sources = mock_reference_sources
        mock_settings.proxy_server = mock_proxy_server_config
        mock_settings.nlp = mock_nlp_config

        mock_config_manager.settings = mock_settings
        mock_get_config_manager.return_value = mock_config_manager

        # Mock get_settings for sense2vec component
        mock_get_settings.return_value = mock_settings

        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.is_proxy_enabled.return_value = True
        mock_proxy_manager.start_proxy.return_value = True
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # Mock spaCy
        mock_nlp = Mock()
        mock_nlp.pipe_names = []  # Make pipe_names iterable
        mock_spacy_load.return_value = mock_nlp

        pipeline = NLPPipeline()

        # Verify concepcy was added with proxy config
        expected_config = {
            "relations_of_interest": ["RELATED_TO", "IS_A", "PART_OF"],
            "filter_missing_text": True,
            "filter_edge_weight": 2.0,
            "url": "http://127.0.0.1:18080/conceptnet/query?node=/c/{lang}/{word}&other=/c/{lang}",
        }
        mock_nlp.add_pipe.assert_any_call("concepcy", config=expected_config)

    @patch("nlp.pipeline.get_settings")
    @patch("nlp.pipeline.get_proxy_manager")
    @patch("nlp.pipeline.spacy.load")
    def test_add_dbpedia_component_with_proxy(
        self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings
    ):
        """Test adding DBpedia Spotlight component with proxy enabled"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": True,
        }
        mock_settings.s2v_config = {"abs_path": "/test/path"}
        mock_settings.get_concepcy_config.return_value = {"test": "config"}
        mock_settings.REFERENCE_API_BUDDY_CONFIG = {
            "server": {"host": "127.0.0.1", "port": 18080}
        }
        mock_get_settings.return_value = mock_settings

        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.is_proxy_enabled.return_value = True
        mock_proxy_manager.start_proxy.return_value = True
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # Mock spaCy
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        pipeline = NLPPipeline()

        # Verify DBpedia Spotlight was added with proxy config
        mock_nlp.add_pipe.assert_any_call(
            "dbpedia_spotlight",
            config={
                "dbpedia_rest_endpoint": "http://127.0.0.1:18080/dbpedia_spotlight"
            },
        )

    @patch("nlp.pipeline.get_settings")
    @patch("nlp.pipeline.get_config_manager")
    @patch("nlp.pipeline.get_proxy_manager")
    @patch("nlp.pipeline.spacy.load")
    def test_add_dbpedia_component_without_proxy(
        self,
        mock_spacy_load,
        mock_get_proxy_manager,
        mock_get_config_manager,
        mock_get_settings,
    ):
        """Test adding DBpedia Spotlight component without proxy"""
        # Mock config manager and settings
        mock_config_manager = Mock()
        mock_settings = Mock()

        # Mock reference sources config for dbpedia_spotlight
        mock_dbpedia_spotlight_config = Mock()
        mock_dbpedia_spotlight_config.enabled = True
        mock_dbpedia_spotlight_config.use_proxy = False
        mock_dbpedia_spotlight_config.upstream_url = (
            "https://api.dbpedia-spotlight.org/en/"
        )

        # Mock conceptnet config (disabled)
        mock_conceptnet_config = Mock()
        mock_conceptnet_config.enabled = False

        # Mock NLP config
        mock_nlp_config = Mock()
        mock_nlp_config.sense2vec_path = "/test/path"

        # Mock proxy server config
        mock_proxy_server_config = Mock()
        mock_proxy_server_config.enabled = False

        # Mock reference sources
        mock_reference_sources = Mock()
        mock_reference_sources.conceptnet = mock_conceptnet_config
        mock_reference_sources.dbpedia_spotlight = mock_dbpedia_spotlight_config

        # Setup settings mock
        mock_settings.reference_sources = mock_reference_sources
        mock_settings.proxy_server = mock_proxy_server_config
        mock_settings.nlp = mock_nlp_config

        mock_config_manager.settings = mock_settings
        mock_get_config_manager.return_value = mock_config_manager

        # Mock get_settings for sense2vec component
        mock_get_settings.return_value = mock_settings

        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.is_proxy_enabled.return_value = False
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # Mock spaCy
        mock_nlp = Mock()
        mock_nlp.pipe_names = []  # Make pipe_names iterable
        mock_spacy_load.return_value = mock_nlp

        pipeline = NLPPipeline()

        # Verify DBpedia Spotlight was added with upstream URL (no proxy)
        expected_config = {
            "dbpedia_rest_endpoint": "https://api.dbpedia-spotlight.org/en/"
        }
        mock_nlp.add_pipe.assert_any_call("dbpedia_spotlight", config=expected_config)

    @patch("nlp.pipeline.get_settings")
    @patch("nlp.pipeline.get_proxy_manager")
    @patch("nlp.pipeline.spacy.load")
    def test_reload_pipeline(
        self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings
    ):
        """Test pipeline reload functionality"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False,
        }
        mock_settings.s2v_config = {"abs_path": "/test/path"}
        mock_settings.get_concepcy_config.return_value = {"test": "config"}
        mock_get_settings.return_value = mock_settings

        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.is_proxy_enabled.return_value = False
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # Mock spaCy
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        pipeline = NLPPipeline()

        # Test reload
        result = pipeline.reload_pipeline()

        assert result is True
        mock_proxy_manager.stop_proxy.assert_called()

    @patch("nlp.pipeline.get_settings")
    @patch("nlp.pipeline.get_proxy_manager")
    @patch("nlp.pipeline.spacy.load")
    def test_shutdown(self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings):
        """Test pipeline shutdown functionality"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False,
        }
        mock_settings.s2v_config = {"abs_path": "/test/path"}
        mock_settings.get_concepcy_config.return_value = {"test": "config"}
        mock_get_settings.return_value = mock_settings

        # Mock proxy manager
        mock_proxy_manager = Mock()
        mock_proxy_manager.is_proxy_enabled.return_value = False
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # Mock spaCy
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        pipeline = NLPPipeline()

        # Test shutdown
        pipeline.shutdown()

        assert not pipeline._initialized
        assert pipeline.nlp is None
        assert pipeline.s2v is None
        mock_proxy_manager.stop_proxy.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])

"""
Unit tests for NLP Pipeline proxy integration.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, patch, MagicMock
from nlp.pipeline import NLPPipeline, get_pipeline


class TestPipelineProxyIntegration:
    """Test cases for NLP Pipeline proxy integration"""

    def setup_method(self):
        """Setup for each test method"""
        # Reset the global pipeline instance
        import nlp.pipeline
        nlp.pipeline._pipeline_instance = None

    @patch('nlp.pipeline.get_settings')
    @patch('nlp.pipeline.get_proxy_manager')
    @patch('nlp.pipeline.spacy.load')
    def test_pipeline_init_with_proxy_disabled(self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings):
        """Test pipeline initialization when proxy is disabled"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False
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

    @patch('nlp.pipeline.get_settings')
    @patch('nlp.pipeline.get_proxy_manager')
    @patch('nlp.pipeline.spacy.load')
    def test_pipeline_init_with_proxy_enabled(self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings):
        """Test pipeline initialization when proxy is enabled"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": True,
            "spacy_dbpedia_spotlight": False
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

    @patch('nlp.pipeline.get_settings')
    @patch('nlp.pipeline.get_proxy_manager')
    def test_pipeline_init_proxy_start_failure(self, mock_get_proxy_manager, mock_get_settings):
        """Test pipeline initialization when proxy fails to start"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": True,
            "spacy_dbpedia_spotlight": False
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

    @patch('nlp.pipeline.get_settings')
    @patch('nlp.pipeline.get_proxy_manager')
    @patch('nlp.pipeline.spacy.load')
    def test_add_concepcy_component_with_proxy(self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings):
        """Test adding concepcy component with proxy enabled"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": True,
            "spacy_dbpedia_spotlight": False
        }
        mock_settings.s2v_config = {"abs_path": "/test/path"}
        mock_settings.get_concepcy_config.return_value = {
            "url": "http://127.0.0.1:18080/conceptnet/query?structure_node=/c/{lang}/{word}&other=/c/{lang}",
            "test": "config"
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
        
        # Verify concepcy was added with proxy config
        mock_settings.get_concepcy_config.assert_called_with(use_proxy=True)
        mock_nlp.add_pipe.assert_any_call("concepcy", config={
            "url": "http://127.0.0.1:18080/conceptnet/query?structure_node=/c/{lang}/{word}&other=/c/{lang}",
            "test": "config"
        })

    @patch('nlp.pipeline.get_settings')
    @patch('nlp.pipeline.get_proxy_manager')
    @patch('nlp.pipeline.spacy.load')
    def test_add_dbpedia_component_with_proxy(self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings):
        """Test adding DBpedia Spotlight component with proxy enabled"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": True
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
        mock_nlp.add_pipe.assert_any_call("dbpedia_spotlight", config={
            "dbpedia_rest_endpoint": "http://127.0.0.1:18080/dbpedia_spotlight"
        })

    @patch('nlp.pipeline.get_settings')
    @patch('nlp.pipeline.get_proxy_manager')
    @patch('nlp.pipeline.spacy.load')
    def test_add_dbpedia_component_without_proxy(self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings):
        """Test adding DBpedia Spotlight component without proxy"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False
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
        
        # Verify DBpedia Spotlight was added without proxy config
        mock_nlp.add_pipe.assert_any_call("dbpedia_spotlight")

    @patch('nlp.pipeline.get_settings')
    @patch('nlp.pipeline.get_proxy_manager')
    @patch('nlp.pipeline.spacy.load')
    def test_reload_pipeline(self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings):
        """Test pipeline reload functionality"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False
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

    @patch('nlp.pipeline.get_settings')
    @patch('nlp.pipeline.get_proxy_manager')
    @patch('nlp.pipeline.spacy.load')
    def test_shutdown(self, mock_spacy_load, mock_get_proxy_manager, mock_get_settings):
        """Test pipeline shutdown functionality"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False
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

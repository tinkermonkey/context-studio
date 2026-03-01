"""
Integration tests for Reference API Proxy functionality.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, Mock
from nlp.proxy_manager import get_proxy_manager


class TestReferenceAPIProxyIntegration:
    """Integration tests for Reference API Proxy"""

    def setup_method(self):
        """Setup for each test method"""
        # Reset the global proxy manager instance
        import nlp.proxy_manager

        nlp.proxy_manager._proxy_manager = None

    def teardown_method(self):
        """Cleanup after each test method"""
        # Stop any running proxy
        try:
            proxy_manager = get_proxy_manager()
            proxy_manager.stop_proxy()
        except Exception:
            pass

    @pytest.mark.integration
    def test_proxy_lifecycle_no_apis_enabled(self):
        """Test proxy lifecycle when no APIs are enabled"""
        with patch("nlp.proxy_manager.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.ENABLE_CACHING_PROXY = {
                "concepcy": False,
                "spacy_dbpedia_spotlight": False,
            }
            mock_settings.get_reference_api_buddy_config.return_value = {
                "server": {"host": "127.0.0.1", "port": 18080},
                "cache": {"database_path": "./test_cache.db"},
                "domain_mappings": {},
                "throttling": {"domain_limits": {}},
            }
            mock_get_settings.return_value = mock_settings

            proxy_manager = get_proxy_manager()

            # Should return True but not actually start proxy
            result = proxy_manager.start_proxy()
            assert result is True
            assert not proxy_manager.is_running

            # Stop should not fail
            proxy_manager.stop_proxy()

    @pytest.mark.integration
    def test_proxy_configuration_validation(self):
        """Test proxy configuration validation"""
        with patch("nlp.proxy_manager.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.ENABLE_CACHING_PROXY = {
                "concepcy": True,
                "spacy_dbpedia_spotlight": False,
            }
            mock_settings.get_reference_api_buddy_config.return_value = {
                "server": {"host": "127.0.0.1", "port": 18080},
                "cache": {"database_path": "./test_cache.db"},
                "domain_mappings": {
                    "conceptnet": {
                        "upstream": "https://api.conceptnet.io",
                        "enabled_keys": ["concepcy", "conceptnet"],
                    }
                },
                "throttling": {
                    "domain_limits": {"conceptnet": 3600, "dbpedia_spotlight": 3600}
                },
            }
            mock_get_settings.return_value = mock_settings

            proxy_manager = get_proxy_manager()
            config = proxy_manager._get_proxy_config()

            # Validate configuration structure
            assert config is not None
            assert "domain_mappings" in config
            assert "server" in config
            assert "cache" in config
            assert "throttling" in config

            # Validate domain mappings
            assert "conceptnet" in config["domain_mappings"]
            assert (
                config["domain_mappings"]["conceptnet"]["upstream"]
                == "https://api.conceptnet.io"
            )

            # Validate throttling
            assert "domain_limits" in config["throttling"]
            assert "conceptnet" in config["throttling"]["domain_limits"]

    @pytest.mark.integration
    def test_proxy_enabled_check(self):
        """Test proxy enabled check functionality"""
        with patch("nlp.proxy_manager.get_settings") as mock_get_settings:
            # Test with no APIs enabled
            mock_settings = Mock()
            mock_settings.ENABLE_CACHING_PROXY = {
                "concepcy": False,
                "spacy_dbpedia_spotlight": False,
            }
            mock_get_settings.return_value = mock_settings

            proxy_manager = get_proxy_manager()
            assert not proxy_manager.is_proxy_enabled()

            # Test with concepcy enabled
            mock_settings.ENABLE_CACHING_PROXY["concepcy"] = True
            assert proxy_manager.is_proxy_enabled()

            # Test with only DBpedia enabled
            mock_settings.ENABLE_CACHING_PROXY = {
                "concepcy": False,
                "spacy_dbpedia_spotlight": True,
            }
            assert proxy_manager.is_proxy_enabled()

    @pytest.mark.integration
    def test_proxy_restart_functionality(self):
        """Test proxy restart functionality"""
        with patch("nlp.proxy_manager.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.ENABLE_CACHING_PROXY = {
                "concepcy": False,
                "spacy_dbpedia_spotlight": False,
            }
            mock_get_settings.return_value = mock_settings

            proxy_manager = get_proxy_manager()

            # Mock the start and stop methods to test restart logic
            with patch.object(
                proxy_manager, "start_proxy", return_value=True
            ) as mock_start, patch.object(proxy_manager, "stop_proxy") as mock_stop:

                result = proxy_manager.restart_proxy()

                mock_stop.assert_called_once()
                mock_start.assert_called_once()
                assert result is True

    @pytest.mark.integration
    def test_error_handling_scenarios(self):
        """Test error handling in various scenarios"""
        with patch("nlp.proxy_manager.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.ENABLE_CACHING_PROXY = {
                "concepcy": True,
                "spacy_dbpedia_spotlight": False,
            }
            mock_settings.get_reference_api_buddy_config.return_value = {
                "server": {"host": "127.0.0.1", "port": 18080},
                "cache": {"database_path": "./test_cache.db"},
                "domain_mappings": {
                    "conceptnet": {
                        "upstream": "https://api.conceptnet.io",
                        "enabled_keys": ["concepcy", "conceptnet"],
                    }
                },
                "throttling": {
                    "domain_limits": {"conceptnet": 3600, "dbpedia_spotlight": 3600}
                },
            }
            mock_get_settings.return_value = mock_settings

            proxy_manager = get_proxy_manager()

            # Test import error handling
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                result = proxy_manager.start_proxy()
                assert result is False
                assert not proxy_manager.is_running
                assert proxy_manager.proxy is None

            # Test stop when not running
            proxy_manager.stop_proxy()  # Should not raise any exceptions

    @pytest.mark.integration
    def test_thread_safety(self):
        """Test thread safety of proxy manager operations"""
        import threading

        with patch("nlp.proxy_manager.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.ENABLE_CACHING_PROXY = {
                "concepcy": False,
                "spacy_dbpedia_spotlight": False,
            }
            mock_get_settings.return_value = mock_settings

            proxy_manager = get_proxy_manager()
            results = []

            def start_proxy():
                results.append(proxy_manager.start_proxy())

            def stop_proxy():
                proxy_manager.stop_proxy()

            # Create multiple threads trying to start/stop proxy
            threads = []
            for i in range(5):
                t1 = threading.Thread(target=start_proxy)
                t2 = threading.Thread(target=stop_proxy)
                threads.extend([t1, t2])

            # Start all threads
            for t in threads:
                t.start()

            # Wait for all threads to complete
            for t in threads:
                t.join()

            # All start_proxy calls should succeed
            assert all(results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

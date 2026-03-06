"""
Unit tests for the Reference API Proxy Manager.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402
from nlp.proxy_manager import ReferenceAPIProxyManager, get_proxy_manager  # noqa: E402, E501


class TestReferenceAPIProxyManager:
    """Test cases for ReferenceAPIProxyManager"""

    def setup_method(self):
        """Setup for each test method"""
        # Reset the global proxy manager instance
        import nlp.proxy_manager

        nlp.proxy_manager._proxy_manager = None

    def test_initialization(self):
        """Test proxy manager initialization"""
        manager = ReferenceAPIProxyManager()

        assert manager.proxy is None
        assert manager.proxy_thread is None
        assert manager.is_running is False
        assert hasattr(manager, "_lock")

    @patch("nlp.proxy_manager.get_settings")
    def test_get_proxy_config_no_apis_enabled(self, mock_get_settings):
        """Test _get_proxy_config when no APIs are enabled."""
        # Mock settings with no APIs enabled
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "conceptnet": False,
            "dbpedia": False,
            "wikidata": False,
        }
        mock_settings.get_reference_api_buddy_config.return_value = {
            "domain_mappings": {
                "conceptnet": {
                    "enabled_keys": ["conceptnet"],
                    "upstream": "https://api.conceptnet.io",
                }
            }
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()
        config = manager._get_proxy_config()

        assert config is None

    @patch("nlp.proxy_manager.get_settings")
    def test_get_proxy_config_concepcy_enabled(self, mock_get_settings):
        """Test proxy config generation when concepcy is enabled"""
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
                    "enabled_keys": ["concepcy"],
                    "upstream": "https://api.conceptnet.io",
                },
                "dbpedia_spotlight": {
                    "enabled_keys": ["spacy_dbpedia_spotlight"],
                    "upstream": "https://api.dbpedia-spotlight.org/en/",
                },
            },
            "throttling": {
                "domain_limits": {"conceptnet": 3600, "dbpedia_spotlight": 3600}  # noqa: E501
            },
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()
        config = manager._get_proxy_config()

        assert config is not None
        assert "domain_mappings" in config
        assert "conceptnet" in config["domain_mappings"]
        assert (
            config["domain_mappings"]["conceptnet"]["upstream"]
            == "https://api.conceptnet.io"
        )
        assert config["throttling"]["domain_limits"]["conceptnet"] == 3600

    @patch("nlp.proxy_manager.get_settings")
    def test_get_proxy_config_dbpedia_enabled(self, mock_get_settings):
        """Test proxy config generation when DBpedia Spotlight is enabled"""
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": True,
        }
        mock_settings.get_reference_api_buddy_config.return_value = {
            "server": {"host": "127.0.0.1", "port": 18080},
            "cache": {"database_path": "./test_cache.db"},
            "domain_mappings": {
                "conceptnet": {
                    "enabled_keys": ["concepcy"],
                    "upstream": "https://api.conceptnet.io",
                },
                "dbpedia_spotlight": {
                    "enabled_keys": ["spacy_dbpedia_spotlight"],
                    "upstream": "https://api.dbpedia-spotlight.org/en/",
                },
            },
            "throttling": {
                "domain_limits": {"conceptnet": 3600, "dbpedia_spotlight": 3600}  # noqa: E501
            },
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()
        config = manager._get_proxy_config()

        assert config is not None
        assert "domain_mappings" in config
        assert "dbpedia_spotlight" in config["domain_mappings"]
        assert (
            config["domain_mappings"]["dbpedia_spotlight"]["upstream"]
            == "https://api.dbpedia-spotlight.org/en/"
        )

    @patch("nlp.proxy_manager.get_settings")
    def test_is_proxy_enabled_false(self, mock_get_settings):
        """Test is_proxy_enabled when no APIs are enabled"""
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False,
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()
        assert manager.is_proxy_enabled() is False

    @patch("nlp.proxy_manager.get_settings")
    def test_is_proxy_enabled_true(self, mock_get_settings):
        """Test is_proxy_enabled when at least one API is enabled"""
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": True,
            "spacy_dbpedia_spotlight": False,
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()
        assert manager.is_proxy_enabled() is True

    @patch("nlp.proxy_manager.get_settings")
    def test_start_proxy_no_apis_enabled(self, mock_get_settings):
        """Test starting proxy when no APIs are enabled"""
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False,
        }
        mock_settings.get_reference_api_buddy_config.return_value = {
            "domain_mappings": {
                "conceptnet": {
                    "enabled_keys": ["concepcy"],
                    "upstream": "https://api.conceptnet.io",
                },
                "dbpedia_spotlight": {
                    "enabled_keys": ["spacy_dbpedia_spotlight"],
                    "upstream": "https://api.dbpedia-spotlight.org/en/",
                },
            }
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()
        result = manager.start_proxy()

        assert result is True
        assert manager.is_running is False

    @patch("nlp.proxy_manager.get_settings")
    def test_start_proxy_already_running(self, mock_get_settings):
        """Test starting proxy when it's already running"""
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": True,
            "spacy_dbpedia_spotlight": False,
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()
        manager.is_running = True

        result = manager.start_proxy()

        assert result is True

    def test_stop_proxy_not_running(self):
        """Test stopping proxy when it's not running"""
        manager = ReferenceAPIProxyManager()

        # Should not raise any exceptions
        manager.stop_proxy()

        assert manager.is_running is False

    def test_singleton_pattern(self):
        """Test that get_proxy_manager returns the same instance"""
        manager1 = get_proxy_manager()
        manager2 = get_proxy_manager()

        assert manager1 is manager2

    @patch("nlp.proxy_manager.get_settings")
    @patch("nlp.proxy_manager.ReferenceAPIProxyManager._wait_for_proxy_ready")
    def test_start_proxy_import_error(self, mock_wait, mock_get_settings):
        """Test starting proxy when reference_api_buddy is not available"""
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
                    "enabled_keys": ["concepcy"],
                    "upstream": "https://api.conceptnet.io",
                },
                "dbpedia_spotlight": {
                    "enabled_keys": ["spacy_dbpedia_spotlight"],
                    "upstream": "https://api.dbpedia-spotlight.org/en/",
                },
            },
            "throttling": {
                "domain_limits": {"conceptnet": 3600, "dbpedia_spotlight": 3600}  # noqa: E501
            },
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()

        # Mock the import to raise ImportError
        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'reference_api_buddy'"),
        ):
            result = manager.start_proxy()

        assert result is False
        assert manager.proxy is None
        assert manager.proxy_thread is None

    @patch("nlp.proxy_manager.get_settings")
    def test_restart_proxy(self, mock_get_settings):
        """Test restarting the proxy"""
        mock_settings = Mock()
        mock_settings.ENABLE_CACHING_PROXY = {
            "concepcy": False,
            "spacy_dbpedia_spotlight": False,
        }
        mock_get_settings.return_value = mock_settings

        manager = ReferenceAPIProxyManager()

        # Mock the stop and start methods
        with patch.object(manager, "stop_proxy") as mock_stop, patch.object(
            manager, "start_proxy", return_value=True
        ) as mock_start:

            result = manager.restart_proxy()

            mock_stop.assert_called_once()
            mock_start.assert_called_once()
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__])

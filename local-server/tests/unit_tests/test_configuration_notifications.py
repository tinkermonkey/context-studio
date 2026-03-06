"""
Unit tests for configuration change notification system
"""

import pytest
import asyncio
import os
import sys
from typing import List, Tuple

# Add the project root to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config_manager, get_config_notifier, ConfigurationNotifier  # noqa: E402, E501


class NotificationCapture:
    """Helper class to capture notifications for testing"""

    def __init__(self):
        self.notifications: List[Tuple[str, any]] = []

    async def async_listener(self, path: str, value):
        """Async notification listener"""
        self.notifications.append((path, value))

    def sync_listener(self, path: str, value):
        """Sync notification listener"""
        self.notifications.append((path, value))

    def clear(self):
        """Clear captured notifications"""
        self.notifications.clear()


class TestConfigurationNotifications:
    """Test configuration change notification system"""

    def setup_method(self):
        """Set up test environment"""
        self.capture = NotificationCapture()

    @pytest.mark.asyncio
    async def test_global_listener_notifications(self):
        """Test that global listeners receive all notifications"""
        config_manager = get_config_manager()
        notifier = get_config_notifier()

        # Register global listener
        notifier.register_global_listener(self.capture.async_listener)

        # Make configuration changes
        config_manager.set("server.port", 9001)
        await asyncio.sleep(0.1)

        config_manager.set("database.check_same_thread", True)
        await asyncio.sleep(0.1)

        # Verify notifications were received
        assert len(self.capture.notifications) >= 2
        paths = [notif[0] for notif in self.capture.notifications]
        assert "server.port" in paths
        assert "database.check_same_thread" in paths

    @pytest.mark.asyncio
    async def test_path_specific_listeners(self):
        """Test that path-specific listeners only receive relevant notifications"""  # noqa: E501
        config_manager = get_config_manager()
        notifier = get_config_notifier()

        # Register path-specific listener
        notifier.register_listener("server.", self.capture.async_listener)

        # Make server and non-server changes
        config_manager.set("server.host", "0.0.0.0")
        await asyncio.sleep(0.1)

        config_manager.set("database.default_url", "test://db")
        await asyncio.sleep(0.1)

        # Should only receive server notification
        server_notifications = [
            notif
            for notif in self.capture.notifications
            if notif[0].startswith("server.")
        ]
        non_server_notifications = [
            notif
            for notif in self.capture.notifications
            if not notif[0].startswith("server.")
        ]

        assert len(server_notifications) >= 1
        assert len(non_server_notifications) == 0

    @pytest.mark.asyncio
    async def test_mixed_sync_async_listeners(self):
        """Test that both sync and async listeners work together"""
        config_manager = get_config_manager()
        notifier = get_config_notifier()

        # Register both sync and async listeners
        notifier.register_global_listener(self.capture.async_listener)
        notifier.register_global_listener(self.capture.sync_listener)

        # Make a configuration change
        config_manager.set("nlp.edge_weight_filter", 1.5)
        await asyncio.sleep(0.1)

        # Should receive notifications from both listeners
        # (may have duplicates but that's expected)
        assert len(self.capture.notifications) >= 1
        nlp_notifications = [
            notif
            for notif in self.capture.notifications
            if notif[0] == "nlp.edge_weight_filter"
        ]
        assert len(nlp_notifications) >= 1

    @pytest.mark.asyncio
    async def test_notification_error_handling(self):
        """Test that notification errors don't break the system"""
        config_manager = get_config_manager()
        notifier = get_config_notifier()

        # Register a listener that will raise an exception
        async def failing_listener(path: str, value):
            raise RuntimeError("Test error in listener")

        notifier.register_global_listener(failing_listener)
        notifier.register_global_listener(
            self.capture.async_listener
        )  # This should still work

        # Make a configuration change
        config_manager.set("server.port", 9002)
        await asyncio.sleep(0.1)

        # The good listener should still receive notifications despite the failing one  # noqa: E501
        assert len(self.capture.notifications) >= 1
        assert any(notif[0] == "server.port" for notif in self.capture.notifications)  # noqa: E501

    def test_notifier_initialization(self):
        """Test that configuration notifier initializes correctly"""
        notifier = ConfigurationNotifier()

        assert isinstance(notifier.listeners, dict)
        assert isinstance(notifier.global_listeners, list)
        assert len(notifier.listeners) == 0
        assert len(notifier.global_listeners) == 0

    def test_listener_registration(self):
        """Test listener registration functionality"""
        notifier = ConfigurationNotifier()

        # Test path-specific registration
        notifier.register_listener("test.path", self.capture.sync_listener)
        assert "test.path" in notifier.listeners
        assert len(notifier.listeners["test.path"]) == 1

        # Test global registration
        notifier.register_global_listener(self.capture.sync_listener)
        assert len(notifier.global_listeners) == 1

    def test_config_manager_set_triggers_notifications(self):
        """Test that ConfigurationManager.set() method includes notification triggering"""  # noqa: E501
        config_manager = get_config_manager()

        # Test that set method returns True for valid operations
        # Use a safe test value that won't break the local config
        result = config_manager.set("nlp.edge_weight_filter", 2.5)
        assert result is True

        # Test that set method returns False for invalid operations
        result = config_manager.set("invalid.path.that.does.not.exist", "value")  # noqa: E501
        assert result is False

    @pytest.mark.asyncio
    async def test_service_specific_handlers_exist(self):
        """Test that service-specific notification handlers are registered"""
        notifier = get_config_notifier()

        # Check that handlers are registered for key configuration sections
        expected_patterns = [
            "server.",
            "database.",
            "nlp.",
            "llm.",
            "reference_sources.",
            "proxy_server.",
        ]

        for pattern in expected_patterns:
            assert pattern in notifier.listeners, f"Missing handler for {pattern}"  # noqa: E501
            assert (
                len(notifier.listeners[pattern]) > 0
            ), f"No handlers registered for {pattern}"

"""
Reference API Buddy proxy manager for caching external API requests.
"""

import threading
import time
from typing import Optional, Dict, Any
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

class ReferenceAPIProxyManager:
    """
    Manages the reference_api_buddy caching proxy lifecycle.
    Handles starting, stopping, and configuration updates.
    """
    
    def __init__(self):
        self.proxy: Optional[object] = None
        self.proxy_thread: Optional[threading.Thread] = None
        self.is_running = False
        self._lock = threading.Lock()
    
    def _get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """Generate reference_api_buddy configuration based on enabled APIs"""
        settings = get_settings()
        enabled_apis = settings.ENABLE_CACHING_PROXY
        base_config = settings.get_reference_api_buddy_config()
        
        # Get configured domain mappings and filter by enabled APIs
        configured_mappings = base_config.get("domain_mappings", {})
        active_mappings = {}
        throttle_limits = {}
        
        for domain_key, domain_config in configured_mappings.items():
            # Check if any of the enabled_keys for this domain are enabled
            enabled_keys = domain_config.get("enabled_keys", [domain_key])
            if any(enabled_apis.get(key, False) for key in enabled_keys):
                # This domain should be active
                active_mappings[domain_key] = {
                    "upstream": domain_config["upstream"]
                }
                
                # Get throttle limit for this domain
                domain_limits = base_config.get("throttling", {}).get("domain_limits", {})
                throttle_limits[domain_key] = domain_limits.get(domain_key, 3600)
        
        # Return None if no APIs are enabled
        if not active_mappings:
            return None
        
        # Build final configuration
        config = base_config.copy()
        config["domain_mappings"] = active_mappings
        
        # Ensure throttling section exists and update limits
        if "throttling" not in config:
            config["throttling"] = {}
        config["throttling"]["domain_limits"] = throttle_limits
        
        return config
    
    def start_proxy(self) -> bool:
        """Start the reference_api_buddy proxy if needed"""
        with self._lock:
            if self.is_running:
                logger.info("Reference API proxy is already running")
                return True
            
            config = self._get_proxy_config()
            if config is None:
                logger.info("No reference APIs enabled for caching proxy")
                return True
            
            try:
                # Import here to avoid dependency issues when not using proxy
                from reference_api_buddy.core.proxy import CachingProxy
                
                logger.info("Starting reference API caching proxy...")
                self.proxy = CachingProxy(config)
                
                # Start proxy in background thread
                self.proxy_thread = threading.Thread(
                    target=self._run_proxy,
                    daemon=True
                )
                self.proxy_thread.start()
                
                # Wait for proxy to start
                self._wait_for_proxy_ready()
                
                self.is_running = True
                logger.info(f"Reference API proxy started on {config['server']['host']}:{config['server']['port']}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start reference API proxy: {e}")
                self.proxy = None
                self.proxy_thread = None
                return False
    
    def stop_proxy(self):
        """Stop the reference_api_buddy proxy"""
        with self._lock:
            if not self.is_running:
                return
            
            try:
                logger.info("Stopping reference API caching proxy...")
                if self.proxy and hasattr(self.proxy, 'stop'):
                    self.proxy.stop()
                
                if self.proxy_thread:
                    self.proxy_thread.join(timeout=5)
                
                self.proxy = None
                self.proxy_thread = None
                self.is_running = False
                logger.info("Reference API proxy stopped")
                
            except Exception as e:
                logger.error(f"Error stopping reference API proxy: {e}")
    
    def restart_proxy(self) -> bool:
        """Restart the proxy (for configuration changes)"""
        logger.info("Restarting reference API proxy...")
        self.stop_proxy()
        return self.start_proxy()
    
    def _run_proxy(self):
        """Run the proxy in background thread"""
        try:
            if self.proxy and hasattr(self.proxy, 'start'):
                self.proxy.start(blocking=True)
        except Exception as e:
            logger.error(f"Reference API proxy error: {e}")
            self.is_running = False
    
    def _wait_for_proxy_ready(self, timeout: int = 10):
        """Wait for proxy to be ready to accept requests"""
        try:
            import requests
        except ImportError:
            logger.warning("Requests not available for proxy health check")
            time.sleep(2)  # Just wait a bit and assume it's ready
            return
        
        settings = get_settings()
        config = settings.get_reference_api_buddy_config()
        host = config["server"]["host"]
        port = config["server"]["port"]
        health_url = f"http://{host}:{port}/admin/health"
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_url, timeout=1)
                if response.status_code == 200:
                    return
            except:
                pass
            time.sleep(1)
        
        # Don't raise error, just log warning as proxy might still work
        logger.warning("Reference API proxy health check failed, but continuing anyway")
    
    def is_proxy_enabled(self) -> bool:
        """Check if any reference APIs have proxy enabled"""
        # Check if proxy is explicitly disabled via environment variable
        import os
        if os.environ.get('DISABLE_REFERENCE_API_PROXY', '').lower() in ('true', '1', 'yes'):
            return False
            
        settings = get_settings()
        enabled_apis = settings.ENABLE_CACHING_PROXY
        return any(enabled_apis.values())
    
    def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """Get the current proxy configuration"""
        if not self.is_running:
            return None
        return self._get_proxy_config()

    def get_monitoring_stats(self) -> Optional[Dict[str, Any]]:
        """Get comprehensive monitoring statistics from the proxy"""
        if not self.is_running or not self.proxy:
            return None
            
        try:
            # Check if proxy has monitoring capabilities
            if not hasattr(self.proxy, 'get_monitoring_manager'):
                logger.warning("Proxy does not have monitoring capabilities")
                return None
                
            monitoring_manager = self.proxy.get_monitoring_manager()
            
            # Collect all monitoring statistics using the updated API structure
            stats = {
                "cache": self._safe_get_stats(monitoring_manager.get_cache_stats),
                "upstream": self._safe_get_stats(monitoring_manager.get_upstream_stats),
                "database": self._safe_get_stats(monitoring_manager.get_database_stats),
                "proxy_health": self._safe_get_stats(monitoring_manager.get_proxy_health),
                "throttling": self._safe_get_stats(monitoring_manager.get_throttling_stats),
                "timestamp": time.time()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting monitoring stats: {e}")
            return None
    
    def _safe_get_stats(self, stats_method) -> Optional[Dict[str, Any]]:
        """Safely call a monitoring stats method and handle errors"""
        try:
            return stats_method()
        except Exception as e:
            logger.warning(f"Error getting stats from {stats_method.__name__}: {e}")
            return {"error": str(e), "available": False}

# Global instance
_proxy_manager: Optional[ReferenceAPIProxyManager] = None
_proxy_manager_lock = threading.Lock()

def get_proxy_manager() -> ReferenceAPIProxyManager:
    """Get the global proxy manager instance (singleton, thread-safe)"""
    global _proxy_manager
    if _proxy_manager is None:
        with _proxy_manager_lock:
            if _proxy_manager is None:
                _proxy_manager = ReferenceAPIProxyManager()
    return _proxy_manager

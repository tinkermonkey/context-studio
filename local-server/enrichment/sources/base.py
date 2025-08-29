"""Abstract base class for reference API sources"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio
import aiohttp
from datetime import datetime, UTC
import logging

from config import SourceConfig, SourceType
from ..exceptions import SourceError, SourceTimeoutError, SourceUnavailableError
from nlp.proxy_manager import get_proxy_manager

logger = logging.getLogger(__name__)


class BaseReferenceSource(ABC):
    def __init__(self, source_type: SourceType, config: SourceConfig):
        self.source_type = source_type
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_base_url(self) -> str:
        if getattr(self.config, 'use_proxy', False):
            proxy_manager = get_proxy_manager()
            if getattr(proxy_manager, 'is_running', False):
                proxy_config = proxy_manager.get_proxy_config()
                if proxy_config and 'domain_mappings' in proxy_config:
                    domain_key = self._get_proxy_domain_key()
                    if domain_key in proxy_config['domain_mappings']:
                        server_config = proxy_config.get('server', {})
                        host = server_config.get('host', '127.0.0.1')
                        port = server_config.get('port', 18080)
                        return f"http://{host}:{port}/{domain_key}"

        return self.config.base_url or self._get_default_base_url()

    @abstractmethod
    def _get_default_base_url(self) -> str:
        pass

    @abstractmethod
    def _get_proxy_domain_key(self) -> str:
        pass

    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        last_error = None
        for attempt in range(getattr(self.config, 'max_retries', 0) + 1):
            try:
                if not self.session:
                    raise SourceError(f"Session not initialized for {self.source_type}")

                logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")
                async with self.session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        if response.content_type and response.content_type.startswith('application/json'):
                            return await response.json()
                        else:
                            text_data = await response.text()
                            return {"raw_data": text_data, "content_type": response.content_type}
                    else:
                        error_text = await response.text()
                        raise SourceError(f"HTTP {response.status}: {error_text}")

            except asyncio.TimeoutError as e:
                last_error = SourceTimeoutError(f"Request timeout for {self.source_type}: {str(e)}")
                if attempt < getattr(self.config, 'max_retries', 0):
                    await asyncio.sleep(2 ** attempt)
                    continue

            except aiohttp.ClientError as e:
                last_error = SourceUnavailableError(f"Connection error for {self.source_type}: {str(e)}")
                if attempt < getattr(self.config, 'max_retries', 0):
                    await asyncio.sleep(2 ** attempt)
                    continue

            except Exception as e:
                last_error = SourceError(f"Unexpected error for {self.source_type}: {str(e)}")
                break

        raise last_error or SourceError(f"Request failed for {self.source_type}")

    def _create_base_response(self, success: bool = True, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "success": success,
            "source": self.source_type.value,
            "retrieved_at": datetime.now(UTC),
            "error": error,
        }

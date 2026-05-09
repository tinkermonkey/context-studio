import subprocess
import sys
from typing import Tuple, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class ModelDownloader:
    """
    Utility class for automatically downloading NLP models and dependencies.
    Supports spaCy models models with automatic detection and download.
    """

    def __init__(self):
        pass

    def is_spacy_model_available(self, model_name: str) -> bool:
        """
        Check if a spaCy model is available locally.

        Args:
            model_name: Name of the spaCy model (e.g., 'en_core_web_lg')

        Returns:
            True if model is available, False otherwise
        """
        try:
            import spacy

            spacy.load(model_name)
            return True
        except OSError:
            return False
        except Exception as e:
            logger.warning(f"Unexpected error checking spaCy model {model_name}: {e}")
            return False

    def download_spacy_model(
        self, model_name: str, timeout: int = 300
    ) -> Tuple[bool, Optional[str]]:
        """
        Download a spaCy model using spacy download command.

        Args:
            model_name: Name of the spaCy model to download
            timeout: Download timeout in seconds (default: 300)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        logger.info(f"Downloading spaCy model: {model_name} (timeout: {timeout}s)")

        try:
            # Run spacy download command
            result = subprocess.run(
                [sys.executable, "-m", "spacy", "download", model_name],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                logger.info(f"Successfully downloaded spaCy model: {model_name}")
                return True, None
            else:
                error_msg = f"spacy download failed with code {result.returncode}: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg

        except subprocess.TimeoutExpired:
            error_msg = f"Timeout downloading spaCy model: {model_name}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error downloading spaCy model {model_name}: {e}"
            logger.error(error_msg)
            return False, error_msg

    def ensure_spacy_model(
        self, model_name: str, auto_download: bool = True, timeout: int = 300
    ) -> Tuple[bool, Optional[str]]:
        """
        Ensure a spaCy model is available, downloading if necessary and enabled.

        Args:
            model_name: Name of the spaCy model
            auto_download: Whether to auto-download if missing
            timeout: Download timeout in seconds (default: 300)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if self.is_spacy_model_available(model_name):
            logger.debug(f"spaCy model {model_name} already available")
            return True, None

        if not auto_download:
            error_msg = (
                f"spaCy model {model_name} not available and auto-download disabled"
            )
            logger.warning(error_msg)
            return False, error_msg

        logger.info(f"spaCy model {model_name} not found, attempting to download...")
        return self.download_spacy_model(model_name, timeout)


# Singleton instance for easy access
_model_downloader: Optional[ModelDownloader] = None


def get_model_downloader() -> ModelDownloader:
    """
    Get the global ModelDownloader instance (singleton, thread-safe).
    """
    global _model_downloader
    if _model_downloader is None:
        _model_downloader = ModelDownloader()
    return _model_downloader

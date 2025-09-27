import os
import subprocess
import sys
import urllib.request
import zipfile
import tarfile
from pathlib import Path
from typing import Tuple, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class ModelDownloader:
    """
    Utility class for automatically downloading NLP models and dependencies.
    Supports spaCy models and sense2vec models with automatic detection and download.
    """

    # Official sense2vec models available for download
    SENSE2VEC_MODELS = {
        "s2v_reddit_2015_md": "https://github.com/explosion/sense2vec/releases/download/v1.0.0/s2v_reddit_2015_md.tar.gz",
        "s2v_reddit_2019_lg": "https://github.com/explosion/sense2vec/releases/download/v2.0.0/s2v_reddit_2019_lg.tar.gz"
    }

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

    def download_spacy_model(self, model_name: str, timeout: int = 300) -> Tuple[bool, Optional[str]]:
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
                timeout=timeout
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

    def is_sense2vec_model_available(self, model_path: str) -> bool:
        """
        Check if a sense2vec model is available at the given path.

        Args:
            model_path: Path to the sense2vec model directory

        Returns:
            True if model is available, False otherwise
        """
        path = Path(model_path)
        if not path.exists() or not path.is_dir():
            return False

        # Check for key files that indicate a valid sense2vec model
        required_files = ["vectors", "cfg"]
        return all((path / file).exists() for file in required_files)

    def download_sense2vec_model(self, model_path: str, model_name: str = "s2v_reddit_2015_md") -> Tuple[bool, Optional[str]]:
        """
        Download a sense2vec model to the specified path.

        Args:
            model_path: Target path for the model
            model_name: Name of the model to download (must be in SENSE2VEC_MODELS)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if model_name not in self.SENSE2VEC_MODELS:
            error_msg = f"Unknown sense2vec model: {model_name}. Available models: {list(self.SENSE2VEC_MODELS.keys())}"
            logger.error(error_msg)
            return False, error_msg

        url = self.SENSE2VEC_MODELS[model_name]
        logger.info(f"Downloading sense2vec model {model_name} from {url}")

        try:
            target_path = Path(model_path)
            downloads_dir = target_path.parent
            downloads_dir.mkdir(parents=True, exist_ok=True)

            # Download the archive
            archive_path = downloads_dir / f"{model_name}.tar.gz"
            logger.info(f"Downloading to: {archive_path}")

            urllib.request.urlretrieve(url, archive_path)
            logger.info(f"Download completed: {archive_path}")

            # Extract the archive
            logger.info(f"Extracting to: {downloads_dir}")
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(downloads_dir)

            # Clean up archive file
            archive_path.unlink()
            logger.info(f"Successfully downloaded and extracted sense2vec model: {model_name}")

            # Verify the model was extracted correctly
            if self.is_sense2vec_model_available(model_path):
                return True, None
            else:
                error_msg = f"sense2vec model {model_name} was downloaded but doesn't appear to be valid at {model_path}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Error downloading sense2vec model {model_name}: {e}"
            logger.error(error_msg)
            return False, error_msg

    def ensure_spacy_model(self, model_name: str, auto_download: bool = True, timeout: int = 300) -> Tuple[bool, Optional[str]]:
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
            error_msg = f"spaCy model {model_name} not available and auto-download disabled"
            logger.warning(error_msg)
            return False, error_msg

        logger.info(f"spaCy model {model_name} not found, attempting to download...")
        return self.download_spacy_model(model_name, timeout)

    def ensure_sense2vec_model(self, model_path: str, auto_download: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Ensure a sense2vec model is available, downloading if necessary and enabled.

        Args:
            model_path: Path to the sense2vec model
            auto_download: Whether to auto-download if missing

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if self.is_sense2vec_model_available(model_path):
            logger.debug(f"sense2vec model already available at {model_path}")
            return True, None

        if not auto_download:
            error_msg = f"sense2vec model not available at {model_path} and auto-download disabled"
            logger.warning(error_msg)
            return False, error_msg

        # Infer model name from path
        model_name = Path(model_path).name
        if model_name not in self.SENSE2VEC_MODELS:
            # Default to the standard reddit model if path doesn't match known models
            model_name = "s2v_reddit_2015_md"
            logger.info(f"Unknown sense2vec model path {model_path}, defaulting to {model_name}")

        logger.info(f"sense2vec model not found at {model_path}, attempting to download {model_name}...")
        return self.download_sense2vec_model(model_path, model_name)


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
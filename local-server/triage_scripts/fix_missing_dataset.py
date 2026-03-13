"""
Fix missing dataset file by recreating it from the configuration.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataset.manager import DatasetManager
from utils.logger import get_logger

logger = get_logger(__name__)


def fix_missing_dataset():
    """Fix missing dataset by recreating it from configuration."""

    # Initialize dataset manager
    dm = DatasetManager()

    # Check if there are any datasets in the config
    datasets_config = dm.datasets_config.get("datasets", {})

    if not datasets_config:
        logger.info("No datasets in configuration. Creating default dataset.")
        dataset = dm.create_dataset("Default Dataset", "default.db")
        logger.info(f"Created default dataset: {dataset.title} ({dataset.id})")
        return

    # Check each dataset to see if the file exists
    # Create a list copy to avoid modifying dict during iteration
    datasets_to_check = list(datasets_config.items())

    for dataset_id, dataset_data in datasets_to_check:
        dataset_path = dm.get_dataset_file_path(dataset_data["filename"])

        if not os.path.exists(dataset_path):
            logger.warning(f"Dataset file missing: {dataset_path}")
            logger.info(f"Recreating dataset: {dataset_data['title']}")

            # Remove from config and recreate
            dm.forget_dataset(dataset_id)
            dataset = dm.create_dataset(dataset_data["title"], dataset_data["filename"])
            logger.info(f"Recreated dataset: {dataset.title} ({dataset.id})")
        else:
            logger.info(f"Dataset file exists: {dataset_path}")


if __name__ == "__main__":
    try:
        fix_missing_dataset()
        print("\n✓ Dataset fix completed successfully")
    except Exception as e:
        print(f"\n✗ Error fixing dataset: {e}")
        sys.exit(1)

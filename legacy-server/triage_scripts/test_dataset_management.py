"""Test dataset management functionality."""

import os
import tempfile
import shutil

# Add the project root to the path
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataset.manager import DatasetManager


def test_dataset_manager():
    """Test basic dataset management functionality."""
    # Create temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    datasets_dir = os.path.join(temp_dir, "datasets")
    config_path = os.path.join(temp_dir, "datasets.json")

    try:
        # Initialize dataset manager
        manager = DatasetManager(
            datasets_config_path=config_path, datasets_directory=datasets_dir
        )

        print(f"Datasets directory: {manager.datasets_directory}")
        print(f"Config path: {manager.config_path}")

        # Test creating a dataset
        print("\nCreating first dataset...")
        dataset1 = manager.create_dataset("Test Dataset 1", "test1.db")
        print(f"Created dataset: {dataset1.title} ({dataset1.id})")

        # Test creating another dataset
        print("\nCreating second dataset...")
        dataset2 = manager.create_dataset("Test Dataset 2", "test2.db")
        print(f"Created dataset: {dataset2.title} ({dataset2.id})")

        # Test listing datasets
        print("\nListing all datasets...")
        datasets = manager.list_datasets()
        for dataset in datasets:
            print(
                f"- {dataset.title}: {dataset.filename} (active: {dataset.id == manager.active_dataset_id})"
            )

        # Test switching datasets
        print("\nSwitching to dataset 2...")
        success = manager.switch_dataset(dataset2.id)
        print(f"Switch successful: {success}")

        # Test getting active dataset
        active = manager.get_active_dataset()
        if active:
            print(f"Active dataset: {active.title}")

        # Test metrics
        print("\nGetting metrics...")
        metrics = manager.get_dataset_metrics(dataset1.id)
        print(f"Dataset 1 metrics: {metrics}")

        print("\nDataset management test completed successfully!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_dataset_manager()

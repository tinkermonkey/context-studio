"""Test FastAPI application with dataset creation."""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.utils import get_dataset_manager
import asyncio


async def test_app_with_datasets():
    """Test FastAPI application with dataset management."""
    try:
        print("Creating FastAPI application...")
        create_app()

        print("Application created successfully!")

        # Get dataset manager
        manager = get_dataset_manager()

        # Create a test dataset
        print("\nCreating test dataset...")
        dataset = manager.create_dataset("API Test Dataset", "api_test.db")
        print(f"Created dataset: {dataset.title} ({dataset.id})")

        # Test the active dataset
        active_dataset = manager.get_active_dataset()
        if active_dataset:
            print(f"\nActive dataset: {active_dataset.title}")
            print(f"Dataset file: {active_dataset.filename}")
            print(f"Schema version: {active_dataset.schema_version}")
            print(f"Metrics: {active_dataset.metrics}")

        # Create another dataset and test switching
        print("\nCreating second dataset...")
        dataset2 = manager.create_dataset("Second Test Dataset", "test2.db")
        print(f"Created dataset: {dataset2.title} ({dataset2.id})")

        # Switch to second dataset
        print("\nSwitching to second dataset...")
        success = manager.switch_dataset(dataset2.id)
        print(f"Switch successful: {success}")

        # Verify active dataset changed
        active_dataset = manager.get_active_dataset()
        if active_dataset:
            print(f"New active dataset: {active_dataset.title}")

        # List all datasets
        datasets = manager.list_datasets()
        print(f"\nTotal datasets: {len(datasets)}")
        for dataset in datasets:
            active_status = (
                " (ACTIVE)" if dataset.id == manager.active_dataset_id else ""
            )
            print(f"- {dataset.title}: {dataset.filename}{active_status}")

        print("\nFastAPI application with datasets test completed successfully!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_app_with_datasets())

"""Test FastAPI application startup with dataset management."""

import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio

from app import create_app


async def test_app_startup():
    """Test FastAPI application startup."""
    try:
        print("Creating FastAPI application...")
        create_app()

        print("Application created successfully!")

        # Test dataset manager initialization
        from database.utils import get_dataset_manager

        manager = get_dataset_manager()

        active_dataset = manager.get_active_dataset()
        if active_dataset:
            print(f"Active dataset: {active_dataset.title}")
            print(f"Dataset file: {active_dataset.filename}")
            print(f"Schema version: {active_dataset.schema_version}")
            print(f"Metrics: {active_dataset.metrics}")
        else:
            print("No active dataset found")

        # List all datasets
        datasets = manager.list_datasets()
        print(f"\nTotal datasets: {len(datasets)}")
        for dataset in datasets:
            print(f"- {dataset.title}: {dataset.filename}")

        print("\nFastAPI application test completed successfully!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_app_startup())

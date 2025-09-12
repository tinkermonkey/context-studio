#!/usr/bin/env python3
"""Simple test script to verify dataset action logging functionality."""

import os
import tempfile
import json

# Add the project root to the path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataset.manager import DatasetManager


def test_dataset_logging():
    """Test that dataset actions are properly logged."""
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "test_datasets.json")
        datasets_dir = os.path.join(temp_dir, "datasets")
        
        # Initialize dataset manager
        dm = DatasetManager(
            datasets_config_path=config_path,
            datasets_directory=datasets_dir
        )
        
        print("1. Testing dataset creation...")
        dataset_info = dm.create_dataset("Test Dataset", "test_dataset.db")
        print(f"   Created dataset: {dataset_info.title} ({dataset_info.id})")
        
        print("2. Testing dataset switching...")
        success = dm.switch_dataset(dataset_info.id)
        print(f"   Switch successful: {success}")
        
        print("3. Testing directory update...")
        new_dir = os.path.join(temp_dir, "new_datasets")
        success = dm.update_datasets_directory(new_dir)
        print(f"   Directory update successful: {success}")
        
        print("4. Testing dataset forgetting...")
        success = dm.forget_dataset(dataset_info.id)
        print(f"   Forget successful: {success}")
        
        print("5. Checking action log...")
        action_log = dm.get_action_log()
        print(f"   Found {len(action_log)} log entries:")
        
        for i, entry in enumerate(action_log, 1):
            print(f"   {i}. {entry['timestamp']}: {entry['action']} - {entry['dataset_title']} ({entry['dataset_id']})")
            if entry['details']:
                print(f"      Details: {entry['details']}")
        
        # Verify log file exists
        log_file_path = dm.action_log_path
        print(f"\n6. Log file location: {log_file_path}")
        print(f"   Log file exists: {os.path.exists(log_file_path)}")
        
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r') as f:
                log_content = json.load(f)
            print(f"   Log file contains {len(log_content)} entries")


if __name__ == "__main__":
    test_dataset_logging()

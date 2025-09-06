#!/usr/bin/env python3
"""
Test Phase 3 Implementation - Comprehensive Testing Suite

This script runs all the Phase 3 tests to validate:
1. Updated unit tests
2. Updated integration tests  
3. New predicate event tests
4. Migration validation (forwards and backwards)
"""

import subprocess
import sys
import os
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_test_suite(test_path, description):
    """Run a test suite and return results."""
    print(f"\n{'='*60}")
    print(f"Running {description}")
    print(f"{'='*60}")
    
    try:
        # Run pytest with detailed output
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            str(test_path),
            "-v",  # verbose output
            "--tb=short",  # short traceback format
            "--color=yes"  # colored output
        ], 
        capture_output=True, 
        text=True, 
        cwd=project_root
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description} - ALL TESTS PASSED")
            return True
        else:
            print(f"❌ {description} - TESTS FAILED (exit code: {result.returncode})")
            return False
            
    except Exception as e:
        print(f"❌ {description} - ERROR RUNNING TESTS: {e}")
        return False


def test_environment_setup():
    """Test that the environment is properly set up."""
    print("🔧 Testing Environment Setup...")
    
    try:
        # Test imports
        from database.models import ChangeEvent
        from database.enums import RecordType
        from services.change_event_handler import ChangeEventHandler
        from utils.event_processor import EventProcessor
        
        print("✅ All required imports successful")
        
        # Test RecordType enum
        assert hasattr(RecordType, 'STRUCTURE_NODE')
        assert hasattr(RecordType, 'STRUCTURE_NODE_LINK')
        assert hasattr(RecordType, 'PREDICATE')
        print("✅ RecordType enum has all required values")
        
        # Test ChangeEvent model
        assert hasattr(ChangeEvent, 'record_type')
        assert hasattr(ChangeEvent, 'record_id')
        print("✅ ChangeEvent model has new fields")
        
        # Test backwards compatibility
        from database.models import NodeEvent
        from services.change_event_handler import NodeEventHandler
        assert NodeEvent == ChangeEvent
        assert NodeEventHandler == ChangeEventHandler
        print("✅ Backwards compatibility aliases work")
        
        return True
        
    except Exception as e:
        print(f"❌ Environment setup failed: {e}")
        return False


def main():
    """Run the complete Phase 3 test suite."""
    print("🧪 Phase 3 Implementation Test Suite")
    print("=" * 60)
    
    start_time = time.time()
    
    # Test environment setup first
    if not test_environment_setup():
        print("\n❌ Environment setup failed. Cannot continue with tests.")
        return False
    
    test_results = []
    
    # 1. Unit Tests - ChangeEventHandler
    test_results.append(run_test_suite(
        "tests/unit_tests/test_change_event_handler.py",
        "Unit Tests - ChangeEventHandler"
    ))
    
    # 2. Unit Tests - EventProcessor (updated)
    test_results.append(run_test_suite(
        "tests/unit_tests/test_event_processor.py", 
        "Unit Tests - EventProcessor (Updated)"
    ))
    
    # 3. Migration Validation Tests
    test_results.append(run_test_suite(
        "tests/unit_tests/test_migration_006_validation.py",
        "Migration Validation Tests (Forward/Backward)"
    ))
    
    # 4. Integration Tests - Change Event System
    test_results.append(run_test_suite(
        "tests/integration_tests/test_change_event_integration.py",
        "Integration Tests - Change Event System"
    ))
    
    # Run legacy test with updated imports (should still work via backwards compatibility)
    legacy_test_path = "tests/unit_tests/test_node_event_handler.py"
    if os.path.exists(legacy_test_path):
        test_results.append(run_test_suite(
            legacy_test_path,
            "Legacy Tests - Backwards Compatibility"
        ))
    
    # Summary
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n{'='*60}")
    print("📊 PHASE 3 TEST SUMMARY")
    print(f"{'='*60}")
    
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"Total Test Suites: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    print(f"Total Runtime: {total_time:.2f} seconds")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL PHASE 3 TESTS PASSED!")
        print("✅ Unit tests updated and working")
        print("✅ Integration tests comprehensive and passing")
        print("✅ Predicate event tests implemented and working")
        print("✅ Migration validation successful (forward/backward)")
        print("✅ Backwards compatibility maintained")
        print("\n🚀 Phase 3: Testing - COMPLETE!")
        return True
    else:
        print(f"\n❌ {total_tests - passed_tests} test suite(s) failed!")
        print("Phase 3 testing needs attention.")
        return False


def run_specific_test_category():
    """Allow running specific test categories."""
    if len(sys.argv) > 1:
        category = sys.argv[1].lower()
        
        test_mapping = {
            "unit": "tests/unit_tests/test_change_event_handler.py",
            "processor": "tests/unit_tests/test_event_processor.py",
            "migration": "tests/unit_tests/test_migration_006_validation.py",
            "integration": "tests/integration_tests/test_change_event_integration.py",
            "legacy": "tests/unit_tests/test_node_event_handler.py"
        }
        
        if category in test_mapping:
            test_environment_setup()
            return run_test_suite(test_mapping[category], f"{category.title()} Tests")
        else:
            print(f"Unknown test category: {category}")
            print(f"Available categories: {', '.join(test_mapping.keys())}")
            return False


if __name__ == "__main__":
    # Check if user wants to run specific test category
    if len(sys.argv) > 1:
        success = run_specific_test_category()
    else:
        success = main()
    
    sys.exit(0 if success else 1)

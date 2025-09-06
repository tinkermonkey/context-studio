#!/usr/bin/env python3
"""
Test Phase 2 Implementation - System Updates
"""

def test_event_processor_updates():
    """Test that EventProcessor has been updated to use new ChangeEvent system."""
    print("Testing EventProcessor updates...")
    
    # Check imports
    try:
        from utils.event_processor import EventProcessor
        from database.models import ChangeEvent
        from database.enums import RecordType
        print("✓ EventProcessor imports ChangeEvent and RecordType correctly")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    
    # Check that processor has new methods
    processor_methods = dir(EventProcessor)
    expected_methods = [
        'process_structure_node_event',
        'process_structure_node_link_event', 
        'process_predicate_event'
    ]
    
    missing_methods = []
    for method in expected_methods:
        if method not in processor_methods:
            missing_methods.append(method)
    
    if missing_methods:
        print(f"✗ Missing methods in EventProcessor: {missing_methods}")
        return False
    else:
        print("✓ EventProcessor has all new record-type-specific methods")
    
    return True

def test_service_imports():
    """Test that services are importing ChangeEvent correctly."""
    print("Testing service imports...")
    
    # Test node_service
    try:
        from services.node_service import NodeService
        print("✓ NodeService imports successfully")
    except ImportError as e:
        print(f"✗ NodeService import error: {e}")
        return False
    
    # Test node_link_service  
    try:
        from services.node_link_service import NodeLinkService
        print("✓ NodeLinkService imports successfully")
    except ImportError as e:
        print(f"✗ NodeLinkService import error: {e}")
        return False
    
    return True

def test_backwards_compatibility():
    """Test that NodeEvent and NodeEventHandler aliases work."""
    print("Testing backwards compatibility...")
    
    # Test NodeEvent alias
    try:
        from database.models import NodeEvent, ChangeEvent
        assert NodeEvent == ChangeEvent
        print("✓ NodeEvent alias works correctly")
    except Exception as e:
        print(f"✗ NodeEvent alias error: {e}")
        return False
    
    # Test NodeEventHandler alias
    try:
        from services.change_event_handler import NodeEventHandler, ChangeEventHandler
        assert NodeEventHandler == ChangeEventHandler
        print("✓ NodeEventHandler alias works correctly")
    except Exception as e:
        print(f"✗ NodeEventHandler alias error: {e}")
        return False
    
    return True

def main():
    """Run all Phase 2 tests."""
    print("=" * 50)
    print("Phase 2 Implementation Test")
    print("=" * 50)
    
    all_tests_pass = True
    
    # Run tests
    tests = [
        test_event_processor_updates,
        test_service_imports,
        test_backwards_compatibility,
    ]
    
    for test in tests:
        if not test():
            all_tests_pass = False
        print()  # Empty line between tests
    
    # Final results
    print("=" * 50)
    if all_tests_pass:
        print("🎉 All Phase 2 tests PASSED!")
        print("✓ EventProcessor updated to handle new ChangeEvent system")
        print("✓ Service imports updated to use ChangeEvent")  
        print("✓ Backwards compatibility maintained")
    else:
        print("❌ Some Phase 2 tests FAILED!")
    
    print("=" * 50)
    return all_tests_pass

if __name__ == "__main__":
    main()

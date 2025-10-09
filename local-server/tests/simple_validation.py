"""Simple validation script to verify implementation without full test framework."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test imports
print("Testing imports...")
try:
    from database.transaction_utils import atomic_transaction, check_optimistic_lock, create_audit_log
    from database.input_validation import sanitize_string, sanitize_json, validate_identifier
    from database.mapping_validation import validate_mapping, create_empty_mapping, add_reference_predicate
    from api.auth_dependencies import get_current_user, UserContext
    from utils.performance_monitoring import PerformanceMonitor, PerformanceTimer
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test input validation
print("\nTesting input validation...")
try:
    # Test HTML sanitization
    result = sanitize_string("<script>alert('xss')</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    print("✓ HTML sanitization works")

    # Test identifier validation
    is_valid, error = validate_identifier("valid_identifier-123")
    assert is_valid
    print("✓ Identifier validation works")

    # Test SQL injection detection
    is_valid, error = validate_identifier("'; DROP TABLE predicates;--")
    assert not is_valid
    print("✓ SQL injection detection works")

    # Test JSON sanitization
    data = {"title": "<b>Test</b>", "count": 42}
    sanitized = sanitize_json(data)
    assert "<b>" not in sanitized["title"]
    print("✓ JSON sanitization works")

except Exception as e:
    print(f"✗ Input validation test failed: {e}")
    sys.exit(1)

# Test mapping validation
print("\nTesting mapping validation...")
try:
    # Test valid mapping
    mapping = create_empty_mapping()
    mapping = add_reference_predicate(
        mapping,
        source="conceptnet",
        source_id="r/RelatedTo",
        title="RelatedTo",
        confidence=0.85
    )
    is_valid, error = validate_mapping(mapping)
    assert is_valid
    print("✓ Valid mapping accepted")

    # Test invalid confidence
    invalid_mapping = create_empty_mapping()
    invalid_mapping["reference_predicates"].append({
        "source": "conceptnet",
        "source_id": "r/RelatedTo",
        "title": "RelatedTo",
        "confidence": 1.5
    })
    is_valid, error = validate_mapping(invalid_mapping)
    assert not is_valid
    print("✓ Invalid confidence rejected")

except Exception as e:
    print(f"✗ Mapping validation test failed: {e}")
    sys.exit(1)

# Test authentication
print("\nTesting authentication...")
try:
    # Test user context creation
    user = UserContext(user_id="test_user", username="Test User", roles=["user"])
    assert user.user_id == "test_user"
    assert "user" in user.roles
    print("✓ User context creation works")

except Exception as e:
    print(f"✗ Authentication test failed: {e}")
    sys.exit(1)

# Test performance monitoring
print("\nTesting performance monitoring...")
try:
    monitor = PerformanceMonitor()
    monitor.set_threshold("test_operation", 100.0)
    monitor.record_metric("test_operation", 50.0)

    stats = monitor.get_statistics("test_operation")
    assert stats is not None
    assert stats["count"] == 1
    assert stats["avg"] == 50.0
    print("✓ Performance monitoring works")

    # Test timer context manager
    with PerformanceTimer("timed_op", monitor) as timer:
        timer.metadata["test"] = "value"

    stats = monitor.get_statistics("timed_op")
    assert stats is not None
    print("✓ Performance timer works")

except Exception as e:
    print(f"✗ Performance monitoring test failed: {e}")
    sys.exit(1)

print("\n" + "="*50)
print("All validation tests passed! ✓")
print("="*50)

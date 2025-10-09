"""
Input validation and sanitization utilities for defense in depth.

This module provides utilities to validate and sanitize user inputs before
they are stored in the database or used in operations.
"""

import json
import re
import html
from typing import Any, Dict, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

# Configuration constants
MAX_JSON_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_STRING_LENGTH = 10000  # Maximum string length for most fields
MAX_IDENTIFIER_LENGTH = 255  # Maximum length for identifiers
MAX_TITLE_LENGTH = 500  # Maximum length for titles


class ValidationError(Exception):
    """Exception raised when input validation fails."""
    pass


def sanitize_string(value: str, max_length: int = MAX_STRING_LENGTH) -> str:
    """
    Sanitize a string value by escaping HTML and limiting length.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Raises:
        ValidationError: If value exceeds maximum length

    Example:
        >>> sanitize_string("<script>alert('xss')</script>")
        "&lt;script&gt;alert('xss')&lt;/script&gt;"
    """
    if not isinstance(value, str):
        raise ValidationError(f"Expected string, got {type(value).__name__}")

    if len(value) > max_length:
        raise ValidationError(
            f"String length {len(value)} exceeds maximum {max_length}"
        )

    # Escape HTML to prevent XSS
    sanitized = html.escape(value)

    return sanitized


def validate_json_size(json_data: Any, max_size: int = MAX_JSON_SIZE_BYTES) -> Tuple[bool, Optional[str]]:
    """
    Validate that JSON data doesn't exceed maximum size.

    Args:
        json_data: Data to validate (dict, list, or JSON string)
        max_size: Maximum allowed size in bytes

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_json_size({"key": "value"})
        (True, None)
        >>> validate_json_size({"key": "x" * 20000000})
        (False, "JSON size exceeds maximum allowed size")
    """
    try:
        # Convert to JSON string if not already
        if isinstance(json_data, str):
            json_str = json_data
        else:
            json_str = json.dumps(json_data)

        # Check size
        size_bytes = len(json_str.encode('utf-8'))

        if size_bytes > max_size:
            return False, f"JSON size {size_bytes} bytes exceeds maximum {max_size} bytes"

        return True, None

    except (TypeError, ValueError) as e:
        return False, f"Invalid JSON data: {str(e)}"


def sanitize_json(json_data: Dict[str, Any], max_size: int = MAX_JSON_SIZE_BYTES) -> Dict[str, Any]:
    """
    Sanitize JSON data by validating size and escaping string values.

    Args:
        json_data: Dictionary to sanitize
        max_size: Maximum allowed size in bytes

    Returns:
        Sanitized dictionary

    Raises:
        ValidationError: If validation fails

    Example:
        >>> sanitize_json({"title": "<b>Test</b>", "count": 42})
        {"title": "&lt;b&gt;Test&lt;/b&gt;", "count": 42}
    """
    if not isinstance(json_data, dict):
        raise ValidationError(f"Expected dict, got {type(json_data).__name__}")

    # Validate size
    is_valid, error_msg = validate_json_size(json_data, max_size)
    if not is_valid:
        raise ValidationError(error_msg)

    # Recursively sanitize string values
    def sanitize_value(value: Any) -> Any:
        if isinstance(value, str):
            # Don't apply max_length to nested strings, just escape HTML
            return html.escape(value)
        elif isinstance(value, dict):
            return {k: sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [sanitize_value(item) for item in value]
        else:
            return value

    sanitized = sanitize_value(json_data)

    return sanitized


def validate_identifier(identifier: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that an identifier follows naming conventions and is safe.

    Rules:
    - Only alphanumeric characters, underscores, hyphens
    - Must start with letter
    - Length between 1 and MAX_IDENTIFIER_LENGTH
    - No SQL injection patterns

    Args:
        identifier: Identifier to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_identifier("valid_identifier-123")
        (True, None)
        >>> validate_identifier("'; DROP TABLE predicates;--")
        (False, "Identifier contains invalid characters")
    """
    if not isinstance(identifier, str):
        return False, f"Identifier must be string, got {type(identifier).__name__}"

    if not identifier or len(identifier) > MAX_IDENTIFIER_LENGTH:
        return False, f"Identifier length must be between 1 and {MAX_IDENTIFIER_LENGTH}"

    # Check pattern: must start with letter, contain only alphanumeric, underscore, hyphen
    pattern = r'^[a-zA-Z][a-zA-Z0-9_-]*$'
    if not re.match(pattern, identifier):
        return False, "Identifier must start with letter and contain only alphanumeric, underscore, hyphen"

    # Check for SQL injection patterns
    sql_patterns = [
        r'(\bDROP\b|\bDELETE\b|\bINSERT\b|\bUPDATE\b|\bSELECT\b)',
        r'(--|;|\/\*|\*\/)',
        r'(\bUNION\b|\bEXEC\b|\bEXECUTE\b)',
    ]

    identifier_upper = identifier.upper()
    for pattern in sql_patterns:
        if re.search(pattern, identifier_upper, re.IGNORECASE):
            return False, "Identifier contains potentially dangerous patterns"

    return True, None


def validate_string_length(value: str, field_name: str, max_length: int) -> None:
    """
    Validate that a string doesn't exceed maximum length.

    Args:
        value: String to validate
        field_name: Name of the field (for error messages)
        max_length: Maximum allowed length

    Raises:
        ValidationError: If string exceeds maximum length

    Example:
        >>> validate_string_length("test", "username", 100)
        None
        >>> validate_string_length("x" * 1000, "username", 100)
        ValidationError: username length exceeds maximum 100 characters
    """
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be string, got {type(value).__name__}")

    if len(value) > max_length:
        raise ValidationError(
            f"{field_name} length {len(value)} exceeds maximum {max_length} characters"
        )


def sanitize_audit_log_value(value: Any) -> Any:
    """
    Sanitize values before storing in audit logs.

    This ensures audit log entries are safe and don't exceed size limits.

    Args:
        value: Value to sanitize (can be dict, list, string, or primitive)

    Returns:
        Sanitized value

    Example:
        >>> sanitize_audit_log_value({"data": "<script>test</script>"})
        {"data": "&lt;script&gt;test&lt;/script&gt;"}
    """
    if value is None:
        return None

    if isinstance(value, dict):
        # Sanitize dictionary
        try:
            return sanitize_json(value, max_size=MAX_JSON_SIZE_BYTES)
        except ValidationError as e:
            logger.warning(f"Audit log value sanitization failed: {e}")
            # Return truncated version if too large
            return {"error": "Value too large for audit log", "type": str(type(value))}

    elif isinstance(value, str):
        # Sanitize string
        try:
            return sanitize_string(value, max_length=MAX_STRING_LENGTH)
        except ValidationError:
            # Truncate if too long
            return sanitize_string(value[:MAX_STRING_LENGTH], max_length=MAX_STRING_LENGTH) + "... [truncated]"

    elif isinstance(value, (list, tuple)):
        # Sanitize list elements
        return [sanitize_audit_log_value(item) for item in value]

    else:
        # Primitive types are safe
        return value


def validate_mapping_structure(mapping: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate basic mapping structure before detailed schema validation.

    This provides a quick validation before the more expensive jsonschema validation.

    Args:
        mapping: Mapping dictionary to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_mapping_structure({"reference_predicates": []})
        (True, None)
    """
    if not isinstance(mapping, dict):
        return False, "Mapping must be a dictionary"

    # Check size
    is_valid, error_msg = validate_json_size(mapping)
    if not is_valid:
        return False, error_msg

    # Check for required keys (basic structure check)
    if "reference_predicates" not in mapping:
        return False, "Mapping must contain 'reference_predicates' key"

    if not isinstance(mapping["reference_predicates"], list):
        return False, "reference_predicates must be a list"

    return True, None


def sanitize_user_input(
    data: Dict[str, Any],
    field_configs: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Sanitize all user input fields in a request.

    Args:
        data: Request data to sanitize
        field_configs: Optional field-specific configuration
                       Format: {"field_name": {"max_length": 100, "required": True}}

    Returns:
        Sanitized data dictionary

    Raises:
        ValidationError: If validation fails

    Example:
        >>> sanitize_user_input(
        ...     {"title": "<b>Test</b>", "age": 25},
        ...     {"title": {"max_length": 100}}
        ... )
        {"title": "&lt;b&gt;Test&lt;/b&gt;", "age": 25}
    """
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data).__name__}")

    field_configs = field_configs or {}
    sanitized = {}

    for key, value in data.items():
        config = field_configs.get(key, {})
        max_length = config.get("max_length", MAX_STRING_LENGTH)

        if value is None:
            sanitized[key] = None
        elif isinstance(value, str):
            try:
                sanitized[key] = sanitize_string(value, max_length=max_length)
            except ValidationError as e:
                raise ValidationError(f"Field '{key}': {str(e)}")
        elif isinstance(value, dict):
            try:
                sanitized[key] = sanitize_json(value)
            except ValidationError as e:
                raise ValidationError(f"Field '{key}': {str(e)}")
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_user_input({"item": item})["item"]
                if isinstance(item, (dict, str))
                else item
                for item in value
            ]
        else:
            # Primitive types are safe
            sanitized[key] = value

    return sanitized

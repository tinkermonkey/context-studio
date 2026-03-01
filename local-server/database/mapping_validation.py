"""
Predicate mapping validation using JSON Schema.

This module provides validation for predicate mapping structures according to ADR-002.
"""

import json
from typing import Dict, Any, Optional
from jsonschema import validate, ValidationError

from utils.logger import get_logger

logger = get_logger(__name__)


# JSON Schema for predicate mapping structure (ADR-002)
MAPPING_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "reference_predicates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["conceptnet", "dbpedia", "wikidata", "schema_org", "manual"]
                    },
                    "source_id": {
                        "type": "string",
                        "minLength": 1
                    },
                    "title": {
                        "type": "string",
                        "minLength": 1
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0
                    }
                },
                "required": ["source", "source_id", "title", "confidence"],
                "additionalProperties": True  # Allow extra fields for source-specific data
            }
        },
        "auto_validated": {
            "type": "boolean",
            "description": "True if confidence >= 0.95 and auto-approved"
        },
        "manual_notes": {
            "type": "string",
            "description": "Optional notes from manual validation"
        }
    },
    "additionalProperties": True  # Allow additional fields for future extensions
}


def validate_mapping(mapping: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate a predicate mapping against the JSON schema.

    Args:
        mapping: Predicate mapping dictionary to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if mapping is valid, False otherwise
        - error_message: Error description if invalid, None if valid

    Example:
        >>> mapping = {
        ...     "reference_predicates": [
        ...         {
        ...             "source": "dbpedia",
        ...             "source_id": "dbo:relatedTo",
        ...             "title": "related to",
        ...             "confidence": 0.87
        ...         }
        ...     ],
        ...     "auto_validated": False
        ... }
        >>> is_valid, error = validate_mapping(mapping)
        >>> if not is_valid:
        ...     print(f"Validation error: {error}")
    """
    if not mapping:
        return False, "Mapping cannot be empty"

    if not isinstance(mapping, dict):
        return False, "Mapping must be a dictionary"

    try:
        validate(instance=mapping, schema=MAPPING_SCHEMA)

        # Additional validation: check confidence score bounds
        if "reference_predicates" in mapping:
            for i, ref_pred in enumerate(mapping["reference_predicates"]):
                conf = ref_pred.get("confidence")
                if conf is not None:
                    if not (0.0 <= conf <= 1.0):
                        return False, f"reference_predicates[{i}].confidence must be between 0.0 and 1.0, got {conf}"

        return True, None

    except ValidationError as e:
        error_msg = f"Schema validation failed: {e.message}"
        logger.warning(f"Mapping validation error: {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected validation error: {str(e)}"
        logger.error(f"Mapping validation exception: {error_msg}")
        return False, error_msg


def validate_mapping_json(mapping_json: str) -> tuple[bool, Optional[str]]:
    """
    Validate a predicate mapping from JSON string.

    Args:
        mapping_json: JSON string containing the mapping

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if mapping is valid, False otherwise
        - error_message: Error description if invalid, None if valid

    Example:
        >>> mapping_json = '{"reference_predicates": [...]}'
        >>> is_valid, error = validate_mapping_json(mapping_json)
    """
    if not mapping_json or not mapping_json.strip():
        return False, "Mapping JSON cannot be empty"

    try:
        mapping = json.loads(mapping_json)
        return validate_mapping(mapping)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON: {str(e)}"
        logger.warning(f"Mapping JSON parse error: {error_msg}")
        return False, error_msg


def validate_confidence_score(confidence: float) -> tuple[bool, Optional[str]]:
    """
    Validate a confidence score.

    Args:
        confidence: Confidence score to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> is_valid, error = validate_confidence_score(0.87)
        >>> assert is_valid
    """
    if not isinstance(confidence, (int, float)):
        return False, f"Confidence must be a number, got {type(confidence).__name__}"

    if not (0.0 <= confidence <= 1.0):
        return False, f"Confidence must be between 0.0 and 1.0, got {confidence}"

    return True, None


def should_auto_validate(mapping: Dict[str, Any]) -> bool:
    """
    Determine if a mapping should be auto-validated based on confidence scores.

    Auto-validation occurs when all reference predicates have confidence >= 0.95.

    Args:
        mapping: Predicate mapping dictionary

    Returns:
        True if mapping should be auto-validated, False otherwise

    Example:
        >>> mapping = {
        ...     "reference_predicates": [
        ...         {"source": "dbpedia", "source_id": "dbo:relatedTo",
        ...          "title": "related to", "confidence": 0.96}
        ...     ]
        ... }
        >>> should_auto_validate(mapping)
        True
    """
    if not mapping or "reference_predicates" not in mapping:
        return False

    ref_preds = mapping["reference_predicates"]
    if not ref_preds:
        return False

    # Check if all confidence scores are >= 0.95
    return all(
        ref_pred.get("confidence", 0.0) >= 0.95
        for ref_pred in ref_preds
    )


def add_reference_predicate(
    mapping: Dict[str, Any],
    source: str,
    source_id: str,
    title: str,
    confidence: float,
    **extra_fields
) -> Dict[str, Any]:
    """
    Add a reference predicate to a mapping.

    This helper function ensures proper structure when adding reference predicates.

    Args:
        mapping: Existing mapping dictionary (will be modified)
        source: Source of the predicate (e.g., "dbpedia", "conceptnet")
        source_id: External ID in the source system
        title: Predicate title/label
        confidence: Confidence score (0.0 to 1.0)
        **extra_fields: Additional source-specific fields

    Returns:
        Updated mapping dictionary

    Raises:
        ValueError: If confidence score is invalid

    Example:
        >>> mapping = {"reference_predicates": []}
        >>> mapping = add_reference_predicate(
        ...     mapping, "dbpedia", "dbo:relatedTo", "related to", 0.87,
        ...     definition="Objects that are related"
        ... )
    """
    # Validate confidence
    is_valid, error = validate_confidence_score(confidence)
    if not is_valid:
        raise ValueError(error)

    # Initialize reference_predicates if needed
    if "reference_predicates" not in mapping:
        mapping["reference_predicates"] = []

    # Create reference predicate entry
    ref_pred = {
        "source": source,
        "source_id": source_id,
        "title": title,
        "confidence": confidence,
        **extra_fields
    }

    mapping["reference_predicates"].append(ref_pred)

    # Update auto_validated flag
    mapping["auto_validated"] = should_auto_validate(mapping)

    return mapping


def create_empty_mapping() -> Dict[str, Any]:
    """
    Create an empty mapping structure.

    Returns:
        Empty mapping dictionary with proper structure

    Example:
        >>> mapping = create_empty_mapping()
        >>> assert "reference_predicates" in mapping
    """
    return {
        "reference_predicates": [],
        "auto_validated": False
    }


def create_manual_mapping(title: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a manual mapping (confidence = 1.0).

    Args:
        title: Title of the manually mapped predicate
        notes: Optional notes about the manual mapping

    Returns:
        Mapping dictionary with manual entry

    Example:
        >>> mapping = create_manual_mapping("related_to", "Manually curated relationship")
    """
    mapping = create_empty_mapping()
    mapping["reference_predicates"] = [
        {
            "source": "manual",
            "source_id": "manual",
            "title": title,
            "confidence": 1.0
        }
    ]
    mapping["auto_validated"] = True  # Manual mappings are automatically validated

    if notes:
        mapping["manual_notes"] = notes

    return mapping

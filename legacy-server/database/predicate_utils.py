"""Utility functions for predicate management."""

import re
import json
import datetime
from typing import List, Optional, cast
from uuid import uuid4
from sqlalchemy.orm import Session
from database.models import Predicate


def generate_identifier_from_title(title: str) -> str:
    """
    Generate a code-safe identifier from a title.
    Converts CamelCase to underscore_lowercase and handles spaces/special chars.  # noqa: E501
    """
    # First, convert CamelCase to underscore_case
    # Insert underscore before uppercase letters that follow lowercase letters or digits  # noqa: E501
    identifier = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", title)
    # Convert to lowercase
    identifier = identifier.lower()
    # Replace whitespace and special characters with underscores
    identifier = re.sub(r"[^\w]", "_", identifier)
    # Remove multiple consecutive underscores
    identifier = re.sub(r"_+", "_", identifier)
    # Remove leading/trailing underscores
    identifier = identifier.strip("_")
    return identifier


def import_conceptnet_predicates(db: Session) -> List[Predicate]:
    """
    Import ConceptNet relations as predicates with proper mapping.
    """
    from config import get_settings

    settings = get_settings()
    relations = settings.concepcy_config["relations_of_interest"]

    predicates = []
    for relation in relations:
        identifier = generate_identifier_from_title(relation)

        # Check if already exists
        existing = db.query(Predicate).filter_by(identifier=identifier).first()
        if existing:
            continue

        # Create mapping
        mapping = {
            "conceptnet": {
                "relation": relation,
                "url": f"https://conceptnet.io/r/{relation}",
                "description": f"ConceptNet relation type: {relation}",
            }
        }

        predicate = Predicate(
            id=str(uuid4()),
            identifier=identifier,
            title=relation,
            definition=f"ConceptNet relation: {relation}",
            mapping=json.dumps(mapping),
            date_created=datetime.datetime.now(datetime.UTC),
            date_modified=datetime.datetime.now(datetime.UTC),
        )

        db.add(predicate)
        predicates.append(predicate)

    db.commit()
    return predicates


def get_conceptnet_relation_for_predicate(
    predicate: Predicate,
) -> Optional[str]:  # noqa: E501
    """
    Extract ConceptNet relation from predicate mapping.
    """
    if not predicate.mapping:
        return None

    try:
        mapping = json.loads(predicate.mapping)  # type: ignore
        return cast(
            Optional[str], mapping.get("conceptnet", {}).get("relation")
        )  # noqa: E501
    except (json.JSONDecodeError, KeyError):
        return None


def validate_term_relationship_predicate(
    subject_domain_id: str,
    object_domain_id: str,
    predicate_id: str,
    db: Session,  # noqa: E501
) -> bool:
    """
    Validate predicate usage for term relationships based on domain predicate sets.  # noqa: E501

    Since predicate_set functionality has been removed, all predicates are now allowed  # noqa: E501
    for all relationships regardless of domain.

    Args:
        subject_domain_id: UUID of the subject term's domain
        object_domain_id: UUID of the object term's domain
        predicate_id: UUID of the predicate to validate
        db: Database session

    Returns:
        bool: True if predicate usage is valid (always True now)
    """
    # With predicate_set removed, all predicates are allowed
    return True


def validate_predicate_identifier(
    identifier: str, predicate_id: Optional[str], db: Session
) -> bool:  # noqa: E501
    """
    Validate that a predicate identifier is unique.

    For new predicates (predicate_id is None), ensures no existing predicate has this identifier.  # noqa: E501
    For updates (predicate_id provided), ensures no other predicate has this identifier.  # noqa: E501

    Args:
        identifier: The predicate identifier to validate
        predicate_id: UUID of predicate being updated (None for new predicates)
        db: Database session

    Returns:
        bool: True if identifier is unique/valid, False otherwise
    """
    query = db.query(Predicate).filter_by(identifier=identifier)

    # For updates, exclude the current predicate from uniqueness check
    if predicate_id:
        query = query.filter(Predicate.id != predicate_id)

    existing = query.first()
    return existing is None

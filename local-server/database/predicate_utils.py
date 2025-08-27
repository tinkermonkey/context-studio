"""Utility functions for predicate management."""

import re
import json
import datetime
from typing import List, Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from database.models import Predicate


def generate_identifier_from_title(title: str) -> str:
    """
    Generate a code-safe identifier from a title.
    Converts CamelCase to underscore_lowercase and handles spaces/special chars.
    """
    # First, convert CamelCase to underscore_case
    # Insert underscore before uppercase letters that follow lowercase letters or digits
    identifier = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', title)
    # Convert to lowercase
    identifier = identifier.lower()
    # Replace whitespace and special characters with underscores
    identifier = re.sub(r'[^\w]', '_', identifier)
    # Remove multiple consecutive underscores
    identifier = re.sub(r'_+', '_', identifier)
    # Remove leading/trailing underscores
    identifier = identifier.strip('_')
    return identifier


def validate_predicate_set(predicate_identifiers: List[str], db: Session) -> bool:
    """
    Validate that all predicate identifiers in a set exist in the database.
    """
    if not predicate_identifiers:
        return True
    
    existing_count = db.query(Predicate).filter(
        Predicate.identifier.in_(predicate_identifiers)
    ).count()
    
    return existing_count == len(predicate_identifiers)


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
                "description": f"ConceptNet relation type: {relation}"
            }
        }
        
        predicate = Predicate(
            id=str(uuid4()),
            identifier=identifier,
            title=relation,
            definition=f"ConceptNet relation: {relation}",
            mapping=json.dumps(mapping),
            date_created=datetime.datetime.now(datetime.UTC),
            date_modified=datetime.datetime.now(datetime.UTC)
        )
        
        db.add(predicate)
        predicates.append(predicate)
    
    db.commit()
    return predicates


def get_conceptnet_relation_for_predicate(predicate: Predicate) -> Optional[str]:
    """
    Extract ConceptNet relation from predicate mapping.
    """
    if not predicate.mapping:
        return None
        
    try:
        mapping = json.loads(predicate.mapping)
        return mapping.get("conceptnet", {}).get("relation")
    except (json.JSONDecodeError, KeyError):
        return None


def validate_term_relationship_predicate(subject_domain_id: str, object_domain_id: str, 
                                        predicate_id: str, db: Session) -> bool:
    """
    Validate predicate usage for term relationships based on domain predicate sets.
    
    When both terms are in the same domain, the predicate must be in that domain's predicate set.
    When terms are in different domains, any predicate is allowed.
    
    Args:
        subject_domain_id: UUID of the subject term's domain
        object_domain_id: UUID of the object term's domain  
        predicate_id: UUID of the predicate to validate
        db: Database session
        
    Returns:
        bool: True if predicate usage is valid, False otherwise
    """
    from database.models import Domain
    
    # If terms are in different domains, allow any predicate
    if subject_domain_id != object_domain_id:
        return True
    
    # Both terms are in the same domain - check domain's predicate set
    domain = db.query(Domain).filter_by(id=subject_domain_id).first()
    if not domain:
        return False
    
    # If domain has no predicate set, allow any predicate
    if not domain.predicate_set:
        return True
    
    try:
        predicate_set = json.loads(domain.predicate_set)
        
        # Handle two formats:
        # 1. List format: ["predicate1", "predicate2"] (newer format from API)
        # 2. Object format: {"predicates": ["predicate1", "predicate2"]} (older format)
        if isinstance(predicate_set, list):
            predicate_identifiers = predicate_set
        elif isinstance(predicate_set, dict):
            predicate_identifiers = predicate_set.get("predicates", [])
        else:
            return False
        
        # Get the predicate identifier
        predicate = db.query(Predicate).filter_by(id=predicate_id).first()
        if not predicate:
            return False
            
        # Check if predicate identifier is in domain's predicate set
        return predicate.identifier in predicate_identifiers
        
    except (json.JSONDecodeError, KeyError):
        return False


def validate_predicate_identifier(identifier: str, predicate_id: Optional[str], db: Session) -> bool:
    """
    Validate that a predicate identifier is unique.
    
    For new predicates (predicate_id is None), ensures no existing predicate has this identifier.
    For updates (predicate_id provided), ensures no other predicate has this identifier.
    
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

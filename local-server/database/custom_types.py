"""
Custom SQLAlchemy Types for Context Studio

This module contains custom SQLAlchemy type decorators that handle
special data type conversions and constraints.
"""

from sqlalchemy.types import TypeDecorator, String
from database.enums import NodeType, RecordType
from typing import Optional


class NodeTypeColumn(TypeDecorator):
    """
    Custom SQLAlchemy type for NodeType enum handling.

    This type decorator properly handles the conversion between
    Python NodeType enum instances and database string values,
    resolving SQLAlchemy enum conversion issues that occur with
    certain versions and configurations.

    Usage:
        node_type = Column(NodeTypeColumn(), nullable=False)
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        Convert Python enum to database string value.

        Args:
            value: NodeType enum instance or string
            dialect: SQLAlchemy dialect

        Returns:
            String value for database storage
        """
        if isinstance(value, NodeType):
            return value.value
        return value

    def process_result_value(self, value: Optional[str], dialect) -> Optional[NodeType]:
        """
        Convert database string value to Python enum.

        During the Phase 1 terminology transition window, this method accepts both
        legacy values (layer, domain, term) and new values (taxonomy, concept_scheme, class).
        The domain.ontology.value_objects.NodeType enum's from_legacy() method provides
        bidirectional mapping to handle this transition.

        Args:
            value: String value from database (old or new terminology)
            dialect: SQLAlchemy dialect

        Returns:
            NodeType enum instance or None

        Raises:
            ValueError: If the value is not a recognized enum value
        """
        if value is not None:
            # Use the domain's NodeType which has from_legacy() for bidirectional mapping
            # This accepts both old (layer, domain, term) and new (taxonomy, concept_scheme, class) values
            try:
                from domain.ontology.value_objects import NodeType as DomainNodeType
                mapped = DomainNodeType.from_legacy(value)
                # Return the legacy enum value for backward compatibility with existing code
                # that expects database.enums.NodeType instances
                legacy_mapping = {
                    DomainNodeType.TAXONOMY: NodeType.LAYER,
                    DomainNodeType.CONCEPT_SCHEME: NodeType.DOMAIN,
                    DomainNodeType.CLASS: NodeType.TERM,
                    DomainNodeType.INDIVIDUAL: NodeType.TERM,  # Fallback for unmapped new types
                }
                return legacy_mapping.get(mapped, NodeType.TERM)
            except (ImportError, ValueError):
                # Fallback to direct enum lookup if domain import fails or value is invalid
                try:
                    return NodeType(value)
                except ValueError:
                    # If it's not in the legacy enum, try a direct mapping for new values
                    new_to_legacy = {
                        "taxonomy": NodeType.LAYER,
                        "concept_scheme": NodeType.DOMAIN,
                        "class": NodeType.TERM,
                        "individual": NodeType.TERM,
                    }
                    mapped_value = new_to_legacy.get(value)
                    if mapped_value is not None:
                        return mapped_value
                    # Re-raise the original ValueError if no mapping exists
                    raise ValueError(
                        f"Unknown node type: {value!r}. "
                        f"Expected one of: layer, domain, term, taxonomy, concept_scheme, class, individual"
                    )
        return value

    def __repr__(self):
        return "NodeTypeColumn()"


class RecordTypeColumn(TypeDecorator):
    """
    Custom SQLAlchemy type for RecordType enum handling.

    This type decorator properly handles the conversion between
    Python RecordType enum instances and database string values,
    resolving SQLAlchemy enum conversion issues that occur with
    certain versions and configurations.

    Usage:
        record_type = Column(RecordTypeColumn(), nullable=False)
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        Convert Python enum to database string value.

        Args:
            value: RecordType enum instance or string
            dialect: SQLAlchemy dialect

        Returns:
            String value for database storage
        """
        if isinstance(value, RecordType):
            return value.value
        return value

    def process_result_value(self, value: Optional[str], dialect) -> Optional[RecordType]:
        """
        Convert database string value to Python enum.

        During the Phase 1 terminology transition window, this method accepts both
        legacy record type values (structure_node, structure_node_link, predicate) and
        new record type values (ontology_entity, relationship, property_definition).

        Args:
            value: String value from database (old or new terminology)
            dialect: SQLAlchemy dialect

        Returns:
            RecordType enum instance or None

        Raises:
            ValueError: If the value is not a recognized enum value
        """
        if value is not None:
            try:
                return RecordType(value)
            except ValueError:
                # Map new terminology back to legacy RecordType for backward compatibility
                new_to_legacy = {
                    "ontology_entity": RecordType.STRUCTURE_NODE,
                    "relationship": RecordType.STRUCTURE_NODE_LINK,
                    "property_definition": RecordType.PREDICATE,
                }
                mapped_value = new_to_legacy.get(value)
                if mapped_value is not None:
                    return mapped_value
                # Re-raise the original ValueError if no mapping exists
                raise ValueError(
                    f"Unknown record type: {value!r}. "
                    f"Expected one of: structure_node, structure_node_link, predicate, "
                    f"ontology_entity, relationship, property_definition"
                )
        return value

    def __repr__(self):
        return "RecordTypeColumn()"


# Future custom types can be added here as needed
# For example:
# class PredicateTypeColumn(TypeDecorator):
#     """Custom type for predicate enums"""
#     pass

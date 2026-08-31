"""
Custom SQLAlchemy Types for Context Studio

This module contains custom SQLAlchemy type decorators that handle
special data type conversions and constraints.
"""


from sqlalchemy.types import String, TypeDecorator

from database.enums import NodeType, RecordType


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

    def process_result_value(self, value: str | None, dialect) -> NodeType | None:
        """
        Convert database string value to Python enum.

        Accepts both legacy values (layer, domain, term) and new values (taxonomy, concept_scheme, class)
        during the terminology transition window. Maps new values to legacy enum instances for
        backward compatibility with existing code.

        Args:
            value: String value from database (old or new terminology)
            dialect: SQLAlchemy dialect

        Returns:
            NodeType enum instance or None

        Raises:
            ValueError: If the value is not a recognized enum value
        """
        if value is not None:
            try:
                # Try legacy enum first (layer, domain, term)
                return NodeType(value)
            except ValueError:
                # Map new terminology to legacy enum for backward compatibility
                new_to_legacy = {
                    "taxonomy": NodeType.LAYER,
                    "concept_scheme": NodeType.DOMAIN,
                    "class": NodeType.TERM,
                    "individual": NodeType.TERM,
                }
                mapped_value = new_to_legacy.get(value)
                if mapped_value is not None:
                    return mapped_value
                # Re-raise if no mapping exists
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

    def process_result_value(
        self, value: str | None, dialect
    ) -> RecordType | None:
        """
        Convert database string value to Python enum.

        Accepts both legacy record type values (structure_node, structure_node_link, predicate) and
        new record type values (ontology_entity, relationship, property_definition) during the
        terminology transition window.

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

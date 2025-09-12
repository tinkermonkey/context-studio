"""
Custom SQLAlchemy Types for Context Studio

This module contains custom SQLAlchemy type decorators that handle
special data type conversions and constraints.
"""

from sqlalchemy.types import TypeDecorator, String
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
    
    def process_result_value(self, value, dialect):
        """
        Convert database string value to Python enum.
        
        Args:
            value: String value from database
            dialect: SQLAlchemy dialect
            
        Returns:
            NodeType enum instance or None
        """
        if value is not None:
            return NodeType(value)
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
    
    def process_result_value(self, value, dialect):
        """
        Convert database string value to Python enum.
        
        Args:
            value: String value from database
            dialect: SQLAlchemy dialect
            
        Returns:
            RecordType enum instance or None
        """
        if value is not None:
            return RecordType(value)
        return value
    
    def __repr__(self):
        return "RecordTypeColumn()"


# Future custom types can be added here as needed
# For example:
# class PredicateTypeColumn(TypeDecorator):
#     """Custom type for predicate enums"""
#     pass

"""
Exception classes for the Graph Analysis domain.

These exceptions represent domain-specific errors that may occur
during graph operations and analysis.
"""


class GraphError(Exception):
    """Base exception for all graph domain errors."""

    pass


class NodeNotFoundError(GraphError):
    """Raised when a requested node does not exist in the graph."""

    def __init__(self, node_id: str) -> None:
        """
        Initialize the exception.

        Args:
            node_id: The ID of the node that was not found
        """
        self.node_id = node_id
        super().__init__(f"Node with id {node_id} not found")


class InvalidAlgorithmError(GraphError):
    """Raised when an unknown algorithm is requested."""

    def __init__(self, algorithm: str, valid_algorithms: list[str]) -> None:
        """
        Initialize the exception.

        Args:
            algorithm: The invalid algorithm name
            valid_algorithms: List of valid algorithm names
        """
        self.algorithm = algorithm
        self.valid_algorithms = valid_algorithms
        super().__init__(
            f"Algorithm '{algorithm}' is not valid. Valid algorithms: {', '.join(valid_algorithms)}"
        )


class SPARQLValidationError(GraphError):
    """Raised when SPARQL query validation fails."""

    def __init__(self, query: str, reason: str) -> None:
        """
        Initialize the exception.

        Args:
            query: The SPARQL query that failed validation
            reason: The reason why validation failed
        """
        self.query = query
        self.reason = reason
        super().__init__(f"SPARQL validation failed: {reason}")


class CommunityDetectionError(GraphError):
    """Raised when community detection fails."""

    def __init__(self, reason: str) -> None:
        """
        Initialize the exception.

        Args:
            reason: The reason why community detection failed
        """
        self.reason = reason
        super().__init__(f"Community detection failed: {reason}")

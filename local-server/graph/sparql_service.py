"""
SPARQL Service for Context Studio Graph Data

This module provides SPARQL query capabilities for the Context Studio graph data
using RDFLib to create an in-memory RDF representation of the SQLite database.
"""

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS
from rdflib.namespace import FOAF, DCTERMS, SKOS
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from datetime import datetime

from database.models import StructureNode, StructureNodeLink
from database.enums import NodeType
from utils.logger import get_logger

logger = get_logger(__name__)


class SPARQLService:
    """
    SPARQL service that builds an in-memory RDF graph from SQLite data
    and provides SPARQL querying capabilities.
    """

    def __init__(self, db_session: Session):
        """
        Initialize the SPARQL service with a database session.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
        self.graph = Graph()
        self._setup_namespaces()
        self._build_graph()

    def _setup_namespaces(self):
        """Set up RDF namespaces for the graph."""
        # Define custom namespace for Context Studio
        self.CS = Namespace("http://context-studio.local/vocab/")
        self.ENTITY = Namespace("http://context-studio.local/entity/")

        # Bind namespaces to prefixes
        self.graph.bind("cs", self.CS)
        self.graph.bind("entity", self.ENTITY)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("skos", SKOS)
        self.graph.bind("dcterms", DCTERMS)
        self.graph.bind("foaf", FOAF)

    def _build_graph(self):
        """Build the RDF graph from structure_nodes table."""
        logger.info("Building RDF graph from structure_nodes table...")

        # Clear existing graph
        self.graph = Graph()
        self._setup_namespaces()

        # Add all structure_nodes from the table
        self._add_structure_nodes()
        self._add_structure_node_links()

        logger.info(f"RDF graph built with {len(self.graph)} triples")

    def _add_structure_nodes(self):
        """Add all structure_nodes from the structure_nodes table to the RDF graph."""
        structure_nodes = self.db_session.query(StructureNode).all()

        for structure_node in structure_nodes:
            node_uri = self.ENTITY[f"{structure_node.node_type.value}/{structure_node.id}"]

            # Add RDF type based on structure_node type
            if structure_node.node_type == NodeType.LAYER:
                self.graph.add((node_uri, RDF.type, self.CS.Layer))
            elif structure_node.node_type == NodeType.DOMAIN:
                self.graph.add((node_uri, RDF.type, self.CS.Domain))
            elif structure_node.node_type == NodeType.TERM:
                self.graph.add((node_uri, RDF.type, self.CS.Term))

            # Basic properties
            self.graph.add((node_uri, RDFS.label, Literal(structure_node.title)))

            if structure_node.definition:
                self.graph.add((node_uri, RDFS.comment, Literal(structure_node.definition)))

            # Hierarchical relationships using parent_node_id
            if structure_node.parent_node_id:
                parent_node: Optional[StructureNode] = (
                    self.db_session.query(StructureNode)
                    .filter(StructureNode.id == structure_node.parent_node_id)
                    .first()
                )
                if parent_node:
                    parent_uri = self.ENTITY[f"{parent_node.node_type.value}/{parent_node.id}"]
                    predicate = self._get_hierarchy_predicate(structure_node)
                    self.graph.add((node_uri, predicate, parent_uri))

                    # Add SKOS relationships for terms
                    if structure_node.node_type == NodeType.TERM and parent_node.node_type == NodeType.TERM:
                        self.graph.add((node_uri, SKOS.broader, parent_uri))
                        self.graph.add((parent_uri, SKOS.narrower, node_uri))

                    # Add layer relationship for terms and domains
                    layer_node = self._get_layer_ancestor(structure_node)
                    if layer_node:
                        layer_uri = self.ENTITY[f"layer/{layer_node.id}"]
                        self.graph.add((node_uri, self.CS.belongsToLayer, layer_uri))

            # Metadata
            if structure_node.created_at:
                self.graph.add((node_uri, DCTERMS.created, Literal(structure_node.created_at)))

            if structure_node.last_modified:
                self.graph.add((node_uri, DCTERMS.modified, Literal(structure_node.last_modified)))

            self.graph.add((node_uri, self.CS.version, Literal(structure_node.version)))

            # Structural predicate reference
            if structure_node.structural_predicate_id:
                self.graph.add(
                    (
                        node_uri,
                        self.CS.structuralPredicate,
                        self.ENTITY[f"predicate/{structure_node.structural_predicate_id}"],
                    )
                )

    def _add_structure_node_links(self):
        """Add structure_node link relationships to the RDF graph."""
        links = self.db_session.query(StructureNodeLink).all()

        for link in links:
            # Get source and target structure_nodes to determine their types
            source_node: Optional[StructureNode] = self.db_session.query(StructureNode).filter(StructureNode.id == link.source_node_id).first()
            target_node: Optional[StructureNode] = self.db_session.query(StructureNode).filter(StructureNode.id == link.target_node_id).first()

            if source_node and target_node:
                source_uri = self.ENTITY[f"{source_node.node_type.value}/{source_node.id}"]
                target_uri = self.ENTITY[f"{target_node.node_type.value}/{target_node.id}"]

                # Create predicate URI from the relationship predicate
                predicate_uri = self.CS[link.predicate]

                # Add the relationship triple
                self.graph.add((source_uri, predicate_uri, target_uri))

                # Add metadata about the link
                if link.created_at:
                    # We could create reified statements here for more complex metadata if needed
                    pass

    def _get_hierarchy_predicate(self, structure_node: StructureNode) -> URIRef:
        """
        Get the appropriate predicate for hierarchical relationships.

        Args:
            structure_node: The structure_node to get the predicate for

        Returns:
            URIRef for the predicate to use
        """
        # Use structural predicate if available, otherwise default to "is_a"
        if structure_node.structural_predicate_id:
            # Get the actual predicate title if available
            # For now, use a structured predicate URI
            return self.CS[f"predicate_{structure_node.structural_predicate_id}"]

        return self.CS["is_a"]  # Default predicate

    def _get_layer_ancestor(self, structure_node: StructureNode) -> Optional[StructureNode]:
        """
        Get the layer ancestor of a structure_node by walking up the hierarchy.

        Args:
            structure_node: The structure_node to find the layer ancestor for

        Returns:
            The layer ancestor structure_node, or None if not found
        """
        current: Optional[StructureNode] = structure_node
        while current:
            if current.node_type == NodeType.LAYER:
                return current

            if current.parent_node_id:
                current = (
                    self.db_session.query(StructureNode).filter(StructureNode.id == current.parent_node_id).first()
                )
            else:
                break

        return None

    def query(self, sparql_query: str, initNs: Optional[Dict[str, Namespace]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SPARQL query against the RDF graph.

        Args:
            sparql_query: The SPARQL query string
            initNs: Optional namespace bindings for the query

        Returns:
            List of result dictionaries
        """
        try:
            # Set up default namespaces if none provided
            if initNs is None:
                initNs = {
                    "cs": self.CS,
                    "entity": self.ENTITY,
                    "rdf": RDF,
                    "rdfs": RDFS,
                    "skos": SKOS,
                    "dcterms": DCTERMS,
                    "foaf": FOAF,
                }

            # Execute the query
            results = self.graph.query(sparql_query, initNs=initNs)

            # Convert results to list of dictionaries
            result_list = []
            for row in results:
                result_dict = {}
                for var_name in results.vars:
                    value = row[var_name]
                    if value is not None:
                        # Convert RDFLib terms to appropriate Python types
                        if hasattr(value, "toPython"):
                            result_dict[str(var_name)] = value.toPython()
                        else:
                            result_dict[str(var_name)] = str(value)
                result_list.append(result_dict)

            return result_list

        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            logger.error(f"Query: {sparql_query}")
            raise

    def refresh(self):
        """Refresh the RDF graph from the database."""
        logger.info("Refreshing RDF graph from database...")
        self._build_graph()

    def get_graph_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the RDF graph.

        Returns:
            Dictionary with graph statistics
        """
        return {
            "total_triples": len(self.graph),
            "total_subjects": len(set(self.graph.subjects())),
            "total_predicates": len(set(self.graph.predicates())),
            "total_objects": len(set(self.graph.objects())),
            "namespaces": dict(self.graph.namespaces()),
            "last_updated": datetime.now().isoformat(),
        }

    def serialize(self, format: str = "turtle") -> str:
        """
        Serialize the RDF graph to a string.

        Args:
            format: Serialization format (turtle, n3, xml, json-ld, etc.)

        Returns:
            Serialized graph as string
        """
        return self.graph.serialize(format=format)

    def find_terms_by_title(self, title: str, exact: bool = False) -> List[Dict[str, Any]]:
        """
        Find terms by title using SPARQL.

        Args:
            title: The title to search for
            exact: Whether to do exact match or partial match

        Returns:
            List of matching terms with their details
        """
        if exact:
            filter_clause = f'FILTER(?title = "{title}")'
        else:
            filter_clause = f'FILTER(CONTAINS(LCASE(?title), LCASE("{title}")))'

        query = f"""
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX entity: <http://context-studio.local/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?term ?title ?definition ?parent ?layer WHERE {{
            ?term a cs:Term ;
                  rdfs:label ?title ;
                  rdfs:comment ?definition .
            OPTIONAL {{
                ?term cs:is_a ?parent .
                FILTER(?parent != ?term)
            }}
            OPTIONAL {{
                ?term cs:belongsToLayer ?layer .
            }}
            {filter_clause}
        }}
        """

        return self.query(query)

    def find_related_terms(self, term_id: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        Find terms related to a given term using SPARQL property paths.

        Args:
            term_id: The ID of the term to find relations for
            max_depth: Maximum depth of relationships to traverse

        Returns:
            List of related terms
        """
        term_uri = f"http://context-studio.local/entity/term/{term_id}"

        # Use SPARQL property paths to find relationships
        query = f"""
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX entity: <http://context-studio.local/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        SELECT ?relatedTerm ?relation ?title ?definition WHERE {{
            VALUES ?startTerm {{ <{term_uri}> }}
            
            {{
                ?startTerm ?relation ?relatedTerm .
                FILTER(?relation != rdf:type && ?relation != rdfs:label && ?relation != rdfs:comment)
            }} UNION {{
                ?relatedTerm ?relation ?startTerm .
                FILTER(?relation != rdf:type && ?relation != rdfs:label && ?relation != rdfs:comment)
            }}
            
            ?relatedTerm a cs:Term ;
                        rdfs:label ?title .
            OPTIONAL {{ ?relatedTerm rdfs:comment ?definition }}
        }}
        """

        return self.query(query)

    def get_domain_hierarchy(self, layer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get the domain hierarchy for a layer or all layers.

        Args:
            layer_id: Optional layer ID to filter by

        Returns:
            List of domains with their hierarchical relationships
        """
        layer_filter = ""
        if layer_id:
            layer_uri = f"http://context-studio.local/entity/layer/{layer_id}"
            layer_filter = f"FILTER(?layer = <{layer_uri}>)"

        query = f"""
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX entity: <http://context-studio.local/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?domain ?domainTitle ?layer ?layerTitle WHERE {{
            ?domain a cs:Domain ;
                   rdfs:label ?domainTitle ;
                   cs:is_a ?layer .
            ?layer a cs:Layer ;
                  rdfs:label ?layerTitle .
            {layer_filter}
        }}
        ORDER BY ?layerTitle ?domainTitle
        """

        return self.query(query)

    def get_structure_nodes_with_embeddings(self) -> List[Dict[str, Any]]:
        """
        Get all structure_nodes that have embeddings using SPARQL.

        Returns:
            List of structure_nodes with embedding information
        """
        query = """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX entity: <http://context-studio.local/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?structure_node ?title ?type ?embedding WHERE {
            ?structure_node rdfs:label ?title ;
                  a ?type ;
                  cs:hasEmbedding ?embedding .
            FILTER(?type = cs:Layer || ?type = cs:Domain || ?type = cs:Term)
        }
        ORDER BY ?type ?title
        """

        return self.query(query)

    def get_structure_node_relationships(self, node_id: str) -> List[Dict[str, Any]]:
        """
        Get all relationships for a specific structure_node using SPARQL.

        Args:
            node_id: The ID of the structure_node to get relationships for

        Returns:
            List of relationships for the structure_node
        """
        # We need to check all possible structure_node types
        queries = []
        for node_type in ["layer", "domain", "term"]:
            node_uri = f"http://context-studio.local/entity/{node_type}/{node_id}"
            queries.append(f"<{node_uri}>")

        node_values = " ".join(queries)

        query = f"""
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX entity: <http://context-studio.local/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?relation ?target ?targetTitle ?targetType WHERE {{
            VALUES ?structure_node {{ {node_values} }}
            
            ?structure_node ?relation ?target .
            ?target rdfs:label ?targetTitle ;
                   a ?targetType .
            
            FILTER(?relation != rdf:type && ?relation != rdfs:label && ?relation != rdfs:comment)
            FILTER(?targetType = cs:Layer || ?targetType = cs:Domain || ?targetType = cs:Term)
        }}
        """

        return self.query(query)

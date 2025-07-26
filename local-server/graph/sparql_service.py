"""
SPARQL Service for Context Studio Graph Data

This module provides SPARQL query capabilities for the Context Studio graph data
using RDFLib to create an in-memory RDF representation of the SQLite database.
"""

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS
from rdflib.namespace import FOAF, DCTERMS, SKOS
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Union
import json
from datetime import datetime

from database.models import Layer, Domain, Term, TermRelationship
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
        """Build the RDF graph from SQLite database data."""
        logger.info("Building RDF graph from database...")
        
        # Clear existing graph
        self.graph = Graph()
        self._setup_namespaces()
        
        # Add layers, domains, and terms
        self._add_layers()
        self._add_domains()
        self._add_terms()
        self._add_term_relationships()
        
        logger.info(f"RDF graph built with {len(self.graph)} triples")
    
    def _add_layers(self):
        """Add layer entities to the RDF graph."""
        layers = self.db_session.query(Layer).all()
        
        for layer in layers:
            layer_uri = self.ENTITY[f"layer/{layer.id}"]
            
            # Basic layer properties
            self.graph.add((layer_uri, RDF.type, self.CS.Layer))
            self.graph.add((layer_uri, RDFS.label, Literal(layer.title)))
            
            if layer.definition:
                self.graph.add((layer_uri, RDFS.comment, Literal(layer.definition)))
            
            if layer.primary_predicate:
                self.graph.add((layer_uri, self.CS.primaryPredicate, Literal(layer.primary_predicate)))
            
            # Metadata
            if layer.created_at:
                self.graph.add((layer_uri, DCTERMS.created, Literal(layer.created_at)))
            
            if layer.last_modified:
                self.graph.add((layer_uri, DCTERMS.modified, Literal(layer.last_modified)))
            
            self.graph.add((layer_uri, self.CS.version, Literal(layer.version)))
    
    def _add_domains(self):
        """Add domain entities to the RDF graph."""
        domains = self.db_session.query(Domain).all()
        
        for domain in domains:
            domain_uri = self.ENTITY[f"domain/{domain.id}"]
            layer_uri = self.ENTITY[f"layer/{domain.layer_id}"]
            
            # Basic domain properties
            self.graph.add((domain_uri, RDF.type, self.CS.Domain))
            self.graph.add((domain_uri, RDFS.label, Literal(domain.title)))
            self.graph.add((domain_uri, RDFS.comment, Literal(domain.definition)))
            
            # Relationship to layer
            layer = self.db_session.query(Layer).filter(Layer.id == domain.layer_id).first()
            predicate = self._get_hierarchy_predicate(layer)
            self.graph.add((domain_uri, predicate, layer_uri))
            
            # Metadata
            if domain.created_at:
                self.graph.add((domain_uri, DCTERMS.created, Literal(domain.created_at)))
            
            if domain.last_modified:
                self.graph.add((domain_uri, DCTERMS.modified, Literal(domain.last_modified)))
            
            self.graph.add((domain_uri, self.CS.version, Literal(domain.version)))
    
    def _add_terms(self):
        """Add term entities to the RDF graph."""
        terms = self.db_session.query(Term).all()
        
        for term in terms:
            term_uri = self.ENTITY[f"term/{term.id}"]
            domain_uri = self.ENTITY[f"domain/{term.domain_id}"]
            layer_uri = self.ENTITY[f"layer/{term.layer_id}"]
            
            # Basic term properties
            self.graph.add((term_uri, RDF.type, self.CS.Term))
            self.graph.add((term_uri, RDFS.label, Literal(term.title)))
            self.graph.add((term_uri, RDFS.comment, Literal(term.definition)))
            
            # Relationships to domain and layer
            layer = self.db_session.query(Layer).filter(Layer.id == term.layer_id).first()
            predicate = self._get_hierarchy_predicate(layer)
            
            self.graph.add((term_uri, predicate, domain_uri))
            self.graph.add((term_uri, self.CS.belongsToLayer, layer_uri))
            
            # Parent-child relationships
            if term.parent_term_id:
                parent_uri = self.ENTITY[f"term/{term.parent_term_id}"]
                self.graph.add((term_uri, predicate, parent_uri))
                # Also add SKOS broader/narrower for semantic compatibility
                self.graph.add((term_uri, SKOS.broader, parent_uri))
                self.graph.add((parent_uri, SKOS.narrower, term_uri))
            
            # Metadata
            if term.created_at:
                self.graph.add((term_uri, DCTERMS.created, Literal(term.created_at)))
            
            if term.last_modified:
                self.graph.add((term_uri, DCTERMS.modified, Literal(term.last_modified)))
            
            self.graph.add((term_uri, self.CS.version, Literal(term.version)))
    
    def _add_term_relationships(self):
        """Add term relationship edges to the RDF graph."""
        relationships = self.db_session.query(TermRelationship).all()
        
        for rel in relationships:
            source_uri = self.ENTITY[f"term/{rel.source_term_id}"]
            target_uri = self.ENTITY[f"term/{rel.target_term_id}"]
            
            # Create predicate URI from the relationship predicate
            predicate_uri = self.CS[rel.predicate]
            
            # Add the relationship triple
            self.graph.add((source_uri, predicate_uri, target_uri))
            
            # Add metadata about the relationship if needed
            # We could create a reified statement here for more complex metadata
    
    def _get_hierarchy_predicate(self, layer: Optional[Layer]) -> URIRef:
        """
        Get the appropriate predicate for hierarchical relationships.
        
        Args:
            layer: The layer object to get the primary predicate from
            
        Returns:
            URIRef for the predicate to use
        """
        if layer and layer.primary_predicate:
            return self.CS[layer.primary_predicate]
        else:
            return self.CS["is_a"]  # Default predicate
    
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
                    'cs': self.CS,
                    'entity': self.ENTITY,
                    'rdf': RDF,
                    'rdfs': RDFS,
                    'skos': SKOS,
                    'dcterms': DCTERMS,
                    'foaf': FOAF
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
                        if hasattr(value, 'toPython'):
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
            "last_updated": datetime.now().isoformat()
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
        
        SELECT ?term ?title ?definition ?domain ?layer WHERE {{
            ?term a cs:Term ;
                  rdfs:label ?title ;
                  rdfs:comment ?definition ;
                  cs:is_a ?domain .
            ?domain cs:is_a ?layer .
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
                FILTER(?relation != rdf:type)
            }} UNION {{
                ?relatedTerm ?relation ?startTerm .
                FILTER(?relation != rdf:type)
            }}
            
            ?relatedTerm a cs:Term ;
                        rdfs:label ?title ;
                        rdfs:comment ?definition .
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
"""
Debug script to investigate hierarchy issues
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import StructureNode
from database.utils import get_db_for_current_dataset
from graph.network_service import NetworkService

# Term ID to debug
TERM_ID = "08b2f588-7082-41d2-af29-9521fe1c3e2a"


def main():
    # Get database session
    db = next(get_db_for_current_dataset())

    # Query the term and its ancestors
    term = db.query(StructureNode).filter(StructureNode.id == TERM_ID).first()

    if not term:
        print(f"Term {TERM_ID} not found!")
        return

    print("\n=== Term Information ===")
    print(f"ID: {term.id}")
    print(f"Title: {term.title}")
    print(f"Type: {term.node_type.value}")
    print(f"Parent ID: {term.parent_node_id}")

    # Get parent (domain)
    if term.parent_node_id:
        domain = (
            db.query(StructureNode)
            .filter(StructureNode.id == term.parent_node_id)
            .first()
        )
        if domain:
            print("\n=== Domain Information ===")
            print(f"ID: {domain.id}")
            print(f"Title: {domain.title}")
            print(f"Type: {domain.node_type.value}")
            print(f"Parent ID: {domain.parent_node_id}")

            # Get grandparent (layer)
            if domain.parent_node_id:
                layer = (
                    db.query(StructureNode)
                    .filter(StructureNode.id == domain.parent_node_id)
                    .first()
                )
                if layer:
                    print("\n=== Layer Information ===")
                    print(f"ID: {layer.id}")
                    print(f"Title: {layer.title}")
                    print(f"Type: {layer.node_type.value}")
                    print(f"Parent ID: {layer.parent_node_id}")

    # Create network service and check graph
    print("\n=== Building NetworkX Graph ===")
    network_service = NetworkService(db)
    network_service._build_graph()

    print(f"Total nodes in graph: {network_service.graph.number_of_nodes()}")
    print(f"Total edges in graph: {network_service.graph.number_of_edges()}")

    # Check if our nodes exist in the graph
    term_graph_id = f"term:{TERM_ID}"
    print("\n=== Checking Graph Nodes ===")
    print(
        f"Term node '{term_graph_id}' exists: {network_service.graph.has_node(term_graph_id)}"
    )

    if term.parent_node_id and domain:
        domain_graph_id = f"{domain.node_type.value}:{domain.id}"
        print(
            f"Domain node '{domain_graph_id}' exists: {network_service.graph.has_node(domain_graph_id)}"
        )

        if domain.parent_node_id and layer:
            layer_graph_id = f"{layer.node_type.value}:{layer.id}"
            print(
                f"Layer node '{layer_graph_id}' exists: {network_service.graph.has_node(layer_graph_id)}"
            )

            # Check for edges
            print("\n=== Checking Graph Edges ===")
            print(
                f"Edge from layer to domain exists: {network_service.graph.has_edge(layer_graph_id, domain_graph_id)}"
            )
            print(
                f"Edge from domain to term exists: {network_service.graph.has_edge(domain_graph_id, term_graph_id)}"
            )

            # List all edges
            print("\n=== All Edges in Graph ===")
            for edge in list(network_service.graph.edges(data=True))[:10]:
                print(f"{edge[0]} -> {edge[1]}: {edge[2]}")

    # Test get_term_hierarchy
    print("\n=== Testing get_term_hierarchy ===")
    hierarchy = network_service.get_term_hierarchy(TERM_ID)
    print(f"Ancestors: {len(hierarchy.get('ancestors', []))}")
    for ancestor in hierarchy.get("ancestors", []):
        print(
            f"  - {ancestor['type']}: {ancestor['title']} (distance: {ancestor['distance']})"
        )

    print(f"Descendants: {len(hierarchy.get('descendants', []))}")
    for descendant in hierarchy.get("descendants", []):
        print(
            f"  - {descendant['type']}: {descendant['title']} (distance: {descendant['distance']})"
        )


if __name__ == "__main__":
    main()

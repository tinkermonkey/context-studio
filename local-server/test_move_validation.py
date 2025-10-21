#!/usr/bin/env python3
"""Quick test script to verify move validation behavior"""

import sys
import uuid
from database.utils import get_db_session
from services.node_service import NodeService

def test_move_to_invalid_parent():
    """Test that moving to an invalid parent raises ValueError"""
    db = get_db_session()
    node_service = NodeService(db)

    try:
        # Create a valid layer
        layer_data = {
            "node_type": "layer",
            "title": f"Test Layer {uuid.uuid4()}"
        }
        layer = node_service.create_node(layer_data)
        print(f"✓ Created layer: {layer.id}")

        # Create a domain in that layer
        domain_data = {
            "node_type": "domain",
            "title": f"Test Domain {uuid.uuid4()}",
            "definition": "Test definition",
            "parent_node_id": str(layer.id)
        }
        domain = node_service.create_node(domain_data)
        print(f"✓ Created domain: {domain.id}")

        # Try to move to an invalid parent
        invalid_parent_id = str(uuid.uuid4())
        print(f"\nAttempting to move domain to invalid parent: {invalid_parent_id}")

        try:
            result = node_service.move_nodes(
                node_ids=[str(domain.id)],
                target_parent_id=invalid_parent_id,
                move_children=True
            )
            print(f"✗ Move succeeded when it should have failed!")
            print(f"  Result: {result}")
            return False
        except ValueError as e:
            print(f"✓ Move correctly raised ValueError: {e}")
            return True

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_move_validation()
    sys.exit(0 if success else 1)

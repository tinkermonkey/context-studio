from uuid import uuid4

# Integration tests use shared session-scoped fixtures for performance:
# - shared_client (session-scoped test client, reused across all tests)
# - client (function-scoped, delegates to shared_client for backwards compatibility)  # noqa: E501
# - db_session (function-scoped, provides clean database state per test)


def create_layer(client):
    unique_title = f"TestLayer_{uuid4()}"
    payload = {
        "node_type": "layer",
        "title": unique_title,
        "definition": "Layer for integration test.",
    }
    response = client.post("/api/structure_nodes/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_domain(client, layer_id, title=None, definition=None):
    unique_title = title if title else f"TestDomain_{uuid4()}"
    unique_definition = definition if definition else "Domain for terms test."
    payload = {
        "node_type": "domain",
        "parent_node_id": layer_id,
        "title": unique_title,
        "definition": unique_definition,
    }
    resp = client.post("/api/structure_nodes/", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_and_get_domain(client):
    layer_id = create_layer(client)
    domain_id = create_domain(
        client,
        layer_id,
        title=f"Physics_{uuid4()}",
        definition="The study of matter and energy.",
    )
    get_resp = client.get(f"/api/structure_nodes/{domain_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["id"] == domain_id
    assert get_data["title"].startswith("Physics_")
    assert get_data["definition"] == "The study of matter and energy."
    assert get_data["node_type"] == "domain"
    assert get_data["parent_node_id"] == layer_id


def test_list_domains(client):
    layer_id = create_layer(client)
    # Create two domains with unique titles
    created_domains = []
    for i in range(2):
        domain_data = {
            "node_type": "domain",
            "parent_node_id": layer_id,
            "title": f"ListTestDomain_{i}_{uuid4()}",
            "definition": f"Definition {i}",
        }
        resp = client.post("/api/structure_nodes/", json=domain_data)
        assert resp.status_code == 201
        created_domains.append(resp.json()["id"])

    # List domains by parent (layer) ID
    resp = client.get(
        f"/api/structure_nodes/?node_type=domain&parent_node_id={layer_id}"
    )
    assert resp.status_code == 200
    data = resp.json()

    # Check pagination response structure
    assert "data" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data

    # Check pagination metadata
    assert data["total"] == 2
    assert data["skip"] == 0
    assert data["limit"] == 50
    assert len(data["data"]) == 2

    # Verify the domains are in the response
    returned_ids = [item["id"] for item in data["data"]]
    assert all(domain_id in returned_ids for domain_id in created_domains)


def test_update_domain(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id, title=f"Chemistry_{uuid4()}")
    update_title = f"AdvancedChemistry_{uuid4()}"
    update = {"title": update_title, "definition": "Advanced study."}
    put_resp = client.put(f"/api/structure_nodes/{domain_id}", json=update)
    assert put_resp.status_code == 200
    assert put_resp.json()["title"] == update_title
    assert put_resp.json()["definition"] == "Advanced study."


def test_delete_domain(client):
    layer_id = create_layer(client)
    domain_id = create_domain(client, layer_id, title=f"Biology_{uuid4()}")
    del_resp = client.delete(f"/api/structure_nodes/{domain_id}")
    assert del_resp.status_code == 204
    # Confirm deletion
    get_resp = client.get(f"/api/structure_nodes/{domain_id}")
    assert get_resp.status_code == 404


def test_find_domain(client):
    layer_id = create_layer(client)
    unique_alpha = f"AlphaDomain_{uuid4()}"
    unique_beta = f"BetaDomain_{uuid4()}"
    _ = create_domain(client, layer_id, title=unique_alpha, definition="Physics")  # noqa: E501
    _ = create_domain(client, layer_id, title=unique_beta, definition="Chemistry")  # noqa: E501

    # Note: The find endpoint is not yet implemented in structure_nodes API
    # This test is commented out until vector search is implemented
    # For now, we'll test the standard listing functionality

    # List domains and verify they exist
    resp = client.get(
        f"/api/structure_nodes/?node_type=domain&parent_node_id={layer_id}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2

    titles = [item["title"] for item in data["data"]]
    assert unique_alpha in titles
    assert unique_beta in titles


def test_find_domain_invalid_created_at(client):
    # This test is not applicable to the current structure_nodes API
    # as the find endpoint returns 501 (not implemented)
    # We'll test invalid query parameters instead

    # Test invalid node_type parameter
    resp = client.get("/api/structure_nodes/?node_type=invalid_type")
    assert resp.status_code == 422  # Validation error for invalid enum value


# Negative test: creating a domain with an invalid parent_node_id (should return 422 for invalid UUID)  # noqa: E501
def test_create_domain_invalid_layer_id(client):
    payload = {
        "node_type": "domain",
        "parent_node_id": "not-a-uuid",
        "title": f"InvalidLayerDomain_{uuid4()}",
        "definition": "Should fail.",
    }
    resp = client.post("/api/structure_nodes/", json=payload)
    assert resp.status_code == 422  # FastAPI returns 422 for invalid UUID


def test_domains_pagination(client):
    layer_id = create_layer(client)

    # Create 3 domains with unique titles
    domains = []
    for i in range(3):
        unique_title = f"PaginationDomain{i:02d}_{uuid4()}"
        domain_data = {
            "node_type": "domain",
            "parent_node_id": layer_id,
            "title": unique_title,
            "definition": f"Pagination test domain {i}",
        }
        resp = client.post("/api/structure_nodes/", json=domain_data)
        assert resp.status_code == 201
        domains.append(resp.json()["id"])

    # Test pagination with limit=2
    resp = client.get(
        f"/api/structure_nodes/?node_type=domain&parent_node_id={layer_id}&limit=2&sort_by=title"  # noqa: E501
    )
    assert resp.status_code == 200
    data = resp.json()

    # Check pagination structure
    assert "data" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data

    # Check first page
    assert data["total"] == 3
    assert data["skip"] == 0
    assert data["limit"] == 2
    assert len(data["data"]) == 2

    # Check that we can determine if more pages exist
    has_more_pages = (data["skip"] + data["limit"]) < data["total"]
    assert has_more_pages is True

    # Test second page
    resp2 = client.get(
        f"/api/structure_nodes/?node_type=domain&parent_node_id={layer_id}&skip=2&limit=2&sort_by=title"  # noqa: E501
    )
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["total"] == 3
    assert data2["skip"] == 2
    assert data2["limit"] == 2
    assert len(data2["data"]) == 1  # Only one item on last page

    # Check that this is the last page
    has_more_pages = (data2["skip"] + data2["limit"]) < data2["total"]
    assert has_more_pages is False

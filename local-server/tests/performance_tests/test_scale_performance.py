"""
Scale Performance Test
Creates a large test dataset and persists the database for future runs and migration validation.
Execute this script directly to create or reuse the scale test database, don't execute via pytest.
The scale can be adjusted via the --scale argument (small, medium, large, xlarge)
Database file: tests/performance_tests/scale_test.db
"""
from math import log
import math
import os
import time
import uuid
import argparse
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app import create_app
from utils.logger import get_logger
from database.utils import init_db, get_engine, get_session_local, init_db
from database.migrations.migration_manager import MigrationManager
from sqlalchemy.orm import sessionmaker
from database.models import StructureNode, StructureNodeLink
import psutil


logger = get_logger('scale_perf_test')

# Global session variable
DB_SESSION = None

DB_PATH = None
SQLALCHEMY_DATABASE_URL = None

def get_persistent_client():
    """
    Create or reuse a persistent test database and apply all migrations.
    """

    first_run = not os.path.exists(DB_PATH)
    engine = get_engine(SQLALCHEMY_DATABASE_URL)
    session_local = get_session_local(engine)
    init_db(engine=engine)

    # Apply migrations to maintain schema
    migration_manager = MigrationManager(DB_PATH)
    success = migration_manager.migrate_to_latest()
    if not success:
        raise RuntimeError("Failed to apply migrations to scale test database")

    if first_run:
        logger.info("Created new scale test database with migrations.")
    else:
        logger.info("Using existing scale test database with migrations.")
    global DB_SESSION
    if DB_SESSION is None:
        SessionLocal = sessionmaker(bind=engine)
        DB_SESSION = SessionLocal()
    app = create_app(engine=engine, session_local=session_local)
    return TestClient(app)

def create_layer(client, title=None):
    logger.debug(f"Creating layer with title: {title}")
    payload = {
        "node_type": "layer",
        "title": title or f"Layer {uuid.uuid4()}",
        "definition": "Scale test layer."
    }
    response = client.post("/api/structure_nodes/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def create_domain(client, parent_node_id, title=None):
    logger.debug(f"Creating domain in layer {parent_node_id}")
    payload = {
        "node_type": "domain",
        "title": title or f"Domain {uuid.uuid4()}",
        "definition": "Scale test domain.",
        "parent_node_id": parent_node_id
    }
    response = client.post("/api/structure_nodes/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def create_term(client, domain, name=None):
    logger.debug(f"Creating term in domain {domain['id']}")
    payload = {
        "node_type": "term",
        "title": name or f"Term {uuid.uuid4()}",
        "definition": "Scale test term.",
        "parent_node_id": domain["id"]
    }
    response = client.post("/api/structure_nodes/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def create_relationship(client, source_node_id, target_node_id):
    logger.debug(f"Creating relationship from node {source_node_id} to node {target_node_id}")
    payload = {
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "relationship_type": "related"
    }
    response = client.post("/api/structure_nodes/links", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def update_node(client, node_id, update_payload):
    response = client.put(f"/api/structure_nodes/{node_id}", json=update_payload)
    assert response.status_code == 200, response.text
    return response.json()

def move_node(client, node_id, move_payload):
    # Move is just an update to parent_node_id
    return update_node(client, node_id, move_payload)

def delete_node(client, node_id):
    response = client.delete(f"/api/structure_nodes/{node_id}")
    assert response.status_code in (200, 204), response.text

def search_node(client, node_type, search_payload):
    # Use the unified structure_nodes endpoint with filtering
    params = {"node_type": node_type}
    if "title" in search_payload:
        params["title"] = search_payload["title"]
    if "limit" in search_payload:
        params["limit"] = search_payload["limit"]
    response = client.get("/api/structure_nodes/", params=params)
    assert response.status_code == 200, response.text
    return response.json()

def populate_scale_test(client, num_layers, num_domains_per_layer, num_terms_per_domain, num_relationships_per_term):
    logger.info("Starting scale test data population:")
    logger.info(f"  - Layers: {num_layers}, Domains per layer: {num_domains_per_layer}, Terms per domain: {num_terms_per_domain}, Relationships per term: {num_relationships_per_term}")

    from database.enums import NodeType
    
    # Layers
    total_layers = num_layers
    current_layer_count = DB_SESSION.query(StructureNode).filter(StructureNode.node_type == NodeType.LAYER).count()
    layer_progress = current_layer_count
    logger.info(f"Total layers to exist: {total_layers}, {current_layer_count} found")
    if current_layer_count < num_layers:
        logger.debug(f"Creating {num_layers - current_layer_count} layers to reach {num_layers}...")
        for i in range(current_layer_count, num_layers):
            title = f"ScaleLayer_{i+1}"
            layer = create_layer(client, title=title)
            layer_progress += 1
            if layer_progress % 100 == 0 or layer_progress == total_layers:
                logger.info(f"Layer progress: {layer_progress}/{total_layers}")

    # Domains
    total_domains = num_layers * num_domains_per_layer
    layers = DB_SESSION.query(StructureNode).filter(StructureNode.node_type == NodeType.LAYER).limit(num_layers).all()
    layers = [{"id": layer.id, "title": layer.title} for layer in layers]
    domains = DB_SESSION.query(StructureNode).filter(StructureNode.node_type == NodeType.DOMAIN).all()
    domains = [{"id": domain.id, "title": domain.title, "parent_node_id": domain.parent_node_id} for domain in domains]
    domain_progress = len(domains)
    logger.info(f"Total domains to exist: {total_domains}, {domain_progress} found")
    for li, layer in enumerate(layers):
        current_domains = DB_SESSION.query(StructureNode).filter(
            StructureNode.node_type == NodeType.DOMAIN, 
            StructureNode.parent_node_id == layer["id"]
        ).count()
        if current_domains < num_domains_per_layer:
            logger.debug(f"Creating {num_domains_per_layer - current_domains} domains for layer {layer['id']}, {current_domains} currently exist")
            for j in range(current_domains, num_domains_per_layer):
                domain = create_domain(client, parent_node_id=layer["id"], title=f"ScaleDomain_{layer['id']}_{j}")
                if j == 0:
                    logger.debug(f"Created first domain for layer {layer['id']}: {domain['title']}")
                domains.append({"id": domain["id"], "title": domain["title"], "parent_node_id": domain["parent_node_id"]})
                domain_progress += 1
                if domain_progress % 100 == 0 or domain_progress == total_domains:
                    logger.info(f"Domain progress: {domain_progress}/{total_domains}")

    # Terms
    total_terms = total_domains * num_terms_per_domain
    terms = DB_SESSION.query(StructureNode).filter(StructureNode.node_type == NodeType.TERM).all()
    terms = [{"id": term.id, "title": term.title, "parent_node_id": term.parent_node_id} for term in terms]
    term_progress = len(terms)
    term_progress_check = math.floor((total_terms / 20) if total_terms > 5000 else (total_terms / 10))
    logger.info(f"Total terms to exist: {total_terms}, {term_progress} found")
    for di, domain in enumerate(domains):
        current_terms_in_domain = DB_SESSION.query(StructureNode).filter(
            StructureNode.node_type == NodeType.TERM, 
            StructureNode.parent_node_id == domain["id"]
        ).count()
        if current_terms_in_domain < num_terms_per_domain:
            logger.debug(f"Creating {num_terms_per_domain - current_terms_in_domain} terms for domain {domain['id']}, {current_terms_in_domain} currently exist")
            for k in range(current_terms_in_domain, num_terms_per_domain):
                term = create_term(client, domain=domain, name=f"ScaleTerm_{domain['id']}_{k}")
                if k == 0:
                    logger.debug(f"Created first term for domain {domain['id']}: {term['title']}")
                terms.append({"id": term["id"], "title": term["title"], "parent_node_id": term["parent_node_id"]})
                term_progress += 1
                if term_progress % term_progress_check == 0 or term_progress == total_terms:
                    logger.info(f"Term progress: {term_progress}/{total_terms} ({round(term_progress / total_terms * 100):.0f}%)")

    # Relationships
    total_relationships = total_terms * num_relationships_per_term
    logger.info(f"Total relationships to exist: {total_relationships}")
    relationship_progress = DB_SESSION.query(StructureNodeLink).count()
    relationship_progress_check = math.floor((total_relationships / 20) if total_relationships > 5000 else (total_relationships / 10))
    for idx, term in enumerate(terms):
        current_relationships = DB_SESSION.query(StructureNodeLink).filter(StructureNodeLink.source_node_id == term["id"]).all()
        current_layer_count = len(current_relationships)
        if current_layer_count < num_relationships_per_term:
            logger.debug(f"Creating {num_relationships_per_term - current_layer_count} relationships for term {term['id']}...")
            for r in range(num_relationships_per_term - current_layer_count):
                target_idx = (idx + r + 1) % len(terms)
                if not any(rel for rel in current_relationships if str(rel.target_node_id) == str(terms[target_idx]["id"])):
                    create_relationship(client, source_node_id=term["id"], target_node_id=terms[target_idx]["id"])
                    relationship_progress += 1
                    if relationship_progress % relationship_progress_check == 0 or relationship_progress == total_relationships:
                        logger.info(f"Relationship progress: {relationship_progress}/{total_relationships} ({round(relationship_progress / total_relationships * 100):.0f}%)")

    logger.info("Hierarchy build complete.")

    return [layers, domains, terms]

def main():
    global DB_SESSION
    parser = argparse.ArgumentParser(description="Scale Performance Test")
    parser.add_argument("--scale", type=str, default="large", help="Scale: small, medium, large, xlarge")
    args = parser.parse_args()
    scale = args.scale.lower()

    if scale == "small":
        num_layers = 2
        num_domains_per_layer = 2
        num_terms_per_domain = 5
        num_relationships_per_term = 2
    elif scale == "medium":
        num_layers = 5
        num_domains_per_layer = 5
        num_terms_per_domain = 10
        num_relationships_per_term = 5
    elif scale == "large":
        num_layers = 7
        num_domains_per_layer = 7
        num_terms_per_domain = 25
        num_relationships_per_term = 7
    elif scale == "xlarge":
        num_layers = 10
        num_domains_per_layer = 10
        num_terms_per_domain = 50
        num_relationships_per_term = 10
    elif scale == "2xlarge":
        num_layers = 15
        num_domains_per_layer = 15
        num_terms_per_domain = 75
        num_relationships_per_term = 10
    else:
        raise ValueError(f"Unknown scale: {scale}")

    db_setup_start = time.time()
    global DB_PATH, SQLALCHEMY_DATABASE_URL
    DB_PATH = os.path.join(os.path.dirname(__file__), f"scale_test_{scale}.db")
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    logger.info(f"Running scale test at scale: {scale}")
    client = get_persistent_client()

    # Memory usage tracking
    mem_stats = {}
    def print_mem_usage(label):
        proc = psutil.Process(os.getpid())
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024) if DB_PATH and os.path.exists(DB_PATH) else 0
        mem_stats[label] = (mem_mb, db_size_mb)
        logger.info(f"[MEM] {label}: Python RSS={mem_mb:.2f} MB, SQLite DB={db_size_mb:.2f} MB")

    print_mem_usage("Start")

    # Populate the scale test database
    [layers, domains, terms] = populate_scale_test(client, num_layers, num_domains_per_layer, num_terms_per_domain, num_relationships_per_term)
    db_setup_end = time.time()
    print_mem_usage("After populate_scale_test")
    logger.info(f"Database setup time: {db_setup_end - db_setup_start:.2f} seconds")

    # Performance test phase: 100 repetitions of CRUD/search for each node type
    repetitions = 100
    timings = {}
    created_nodes = {"layer": [], "domain": [], "term": []}
    for node_type, node_list in zip(["layer", "domain", "term"], [layers, domains, terms]):
        logger.info(f"Executing performance test for {node_type}s...")

        # Create
        start = time.time()
        for i in range(repetitions):
            node_id = str(uuid.uuid4())
            if node_type == "layer":
                created_nodes["layer"].append(create_layer(client, title=f"PerfLayer_{node_id}"))
            elif node_type == "domain":
                parent_node_id = layers[i % len(layers)]["id"]
                created_nodes["domain"].append(create_domain(client, parent_node_id=parent_node_id, title=f"PerfDomain_{node_id}"))
            elif node_type == "term":
                domain = domains[i % len(domains)]
                created_nodes["term"].append(create_term(client, domain=domain, name=f"PerfTerm_{node_id}"))
        timings[f"{node_type}_create"] = time.time() - start
        #print_mem_usage(f"After {node_type} create")

        # Update
        start = time.time()
        for i in range(repetitions):
            node = node_list[i % len(node_list)]
            update_payload = {"title": f"Updated_{node_type}_{i}"}
            update_node(client, node["id"], update_payload)
        timings[f"{node_type}_update"] = time.time() - start
        #print_mem_usage(f"After {node_type} update")

        # Move
        start = time.time()
        for i in range(repetitions):
            node = node_list[i % len(node_list)]
            if node_type == "domain":
                # Move domain to another layer
                new_parent_id = layers[(i + 1) % len(layers)]["id"]
                move_payload = {"parent_node_id": new_parent_id}
                move_node(client, node["id"], move_payload)
            elif node_type == "term":
                # Move term to another domain
                new_parent_id = domains[(i + 1) % len(domains)]["id"]
                move_payload = {"parent_node_id": new_parent_id}
                move_node(client, node["id"], move_payload)
        timings[f"{node_type}_move"] = time.time() - start
        #print_mem_usage(f"After {node_type} move")

        # Search
        start = time.time()
        for i in range(repetitions):
            search_payload = {"title": node_list[i % len(node_list)]["title"], "limit": 10}
            search_node(client, node_type, search_payload)
        timings[f"{node_type}_search"] = time.time() - start
        #print_mem_usage(f"After {node_type} search")

        print_mem_usage(f"After {node_type} operations")

    # Delete in reverse order since cascade deletes happen
    for node_type, node_list in zip(["term", "domain", "layer"], [created_nodes["term"], created_nodes["domain"], created_nodes["layer"]]):
        logger.info(f"Deleting {len(node_list)} {node_type}s...")
        start = time.time()
        for i, node in enumerate(node_list):
            try:
                delete_node(client, node["id"])
            except Exception as e:
                logger.error(f"Failed to delete {node_type} {node['id']}: {e}")

        timings[f"{node_type}_delete"] = time.time() - start
        #print_mem_usage(f"After {node_type} delete")

    logger.info(f"============ Performance Summary ======================================")
    logger.info(f"{'Scale:':>30} {scale}")
    logger.info(f"{'Layers:':>30} {num_layers}")
    logger.info(f"{'Domains:':>30} {num_domains_per_layer} per layer, {num_domains_per_layer * num_layers} total")
    logger.info(f"{'Terms:':>30} {num_terms_per_domain} per domain, {num_terms_per_domain * num_domains_per_layer * num_layers} total")
    logger.info(f"{'Relationships:':>30} {num_relationships_per_term} per term, {num_relationships_per_term * num_terms_per_domain * num_domains_per_layer * num_layers} total")
    logger.info(f"{'Total records:':>30} {num_layers * num_domains_per_layer * num_terms_per_domain + num_terms_per_domain * num_relationships_per_term}")
    logger.info(f"{'Iterations:':>30} {repetitions}")
    logger.info(f"{'Total time for iterations:':>30} {sum(timings.values()):.2f} seconds")
    logger.info(f"{'Database setup time:':>30} {db_setup_end - db_setup_start:.2f} seconds")
    logger.info(f"=======================================================================")

    # log table headers
    header_row= "             "
    for op in ["create", "update", "move", "delete", "search"]:
        header_row += f"{op.capitalize():<12}"
    logger.info(header_row)
    logger.info(f"-----------------------------------------------------------------------")

    for node_type in ["layer", "domain", "term"]:
        op_row = ""
        for op in ["create", "update", "move", "delete", "search"]:
            # Each op was run 'repetitions' times
            avg_time = timings[f"{node_type}_{op}"] / repetitions
            op_avg = f"{avg_time:.4f}s/op"
            op_row += f"{op_avg:<12}"
        row_lead = f"{node_type.capitalize()} avg: "
        logger.info(f"{row_lead:>13}{op_row}")
    logger.info("========================================================================")

    # Memory usage summary
    initial_mem, initial_db = mem_stats.get("Start", (None, None))
    final_mem, final_db = mem_stats.get(f"After term delete", (None, None))
    if initial_mem is not None and final_mem is not None:
        logger.info(f"[MEM][SUMMARY] Python RSS delta: {final_mem - initial_mem:.2f} MB (from {initial_mem:.2f} MB to {final_mem:.2f} MB)")
    if initial_db is not None and final_db is not None:
        logger.info(f"[MEM][SUMMARY] SQLite DB size delta: {final_db - initial_db:.2f} MB (from {initial_db:.2f} MB to {final_db:.2f} MB)")

    logger.info("Scale performance test completed.")

if __name__ == "__main__":
    main()

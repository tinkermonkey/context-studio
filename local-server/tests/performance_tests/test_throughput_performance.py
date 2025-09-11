"""
Throughput Performance Test
Measures time to create 100 layers, domains, and terms (with vectors).
Uses a temporary database for each run.
"""

import sys
import os
import time
import uuid
import logging
import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("throughput_perf_test")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

"""
This test uses the shared client fixture from conftest.py, which provides a migrated test database per test.
"""


def create_layer(client, title=None):
    payload = {
        "title": title or f"Layer {uuid.uuid4()}",
        "definition": "Throughput test layer.",
    }
    response = client.post("/api/layers/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_domain(client, layer_id, title=None):
    payload = {
        "title": title or f"Domain {uuid.uuid4()}",
        "definition": "Throughput test domain.",
        "layer_id": layer_id,
    }
    response = client.post("/api/domains/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_term(client, domain, name=None):
    payload = {
        "name": name or f"Term {uuid.uuid4()}",
        "title": name or f"Term {uuid.uuid4()}",
        "definition": "Throughput test term.",
        "domain_id": domain["id"],
        "layer_id": domain["layer_id"],
    }
    response = client.post("/api/terms/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_throughput_performance(client):
    mem_stats = {}

    def print_mem_usage(label):
        proc = psutil.Process(os.getpid())
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        logger.info(f"[THROUGHPUT][MEM] {label}: Python RSS={mem_mb:.2f} MB")
        mem_stats[label] = mem_mb

    print_mem_usage("Start")
    num_layers = 100
    num_domains = 100
    num_terms = 100
    timings = {}
    start = time.time()
    timings["start"] = start

    # Create layers
    layers = []
    for i in range(num_layers):
        layer = create_layer(client, title=f"PerfLayer_{i}")
        layers.append(layer)
        if (i + 1) % 10 == 0 or (i + 1) == num_layers:
            logger.info(f"[THROUGHPUT] Created {i + 1}/{num_layers} layers...")
    timings["layers"] = time.time()
    print_mem_usage("After layers")

    # Create domains
    domains = []
    for i in range(num_domains):
        layer = layers[i % num_layers]
        domain = create_domain(client, layer_id=layer["id"], title=f"PerfDomain_{i}")
        domains.append(domain)
        if (i + 1) % 10 == 0 or (i + 1) == num_domains:
            logger.info(f"[THROUGHPUT] Created {i + 1}/{num_domains} domains...")
    timings["domains"] = time.time()
    print_mem_usage("After domains")

    # Create terms
    terms = []
    for i in range(num_terms):
        domain = domains[i % num_domains]
        term = create_term(client, domain=domain, name=f"PerfTerm_{i}")
        terms.append(term)
        if (i + 1) % 10 == 0 or (i + 1) == num_terms:
            logger.info(f"[THROUGHPUT] Created {i + 1}/{num_terms} terms...")
    timings["terms"] = time.time()
    print_mem_usage("After terms")

    # Performance summary
    logger.info("\n[THROUGHPUT] Performance Summary:")
    logger.info(
        f"  Layers creation:   {timings['layers'] - timings['start']:.2f}s  ({1000*(timings['layers']-timings['start'])/num_layers:.1f} ms/op)"
    )
    logger.info(
        f"  Domains creation:  {timings['domains'] - timings['layers']:.2f}s  ({1000*(timings['domains']-timings['layers'])/num_domains:.1f} ms/op)"
    )
    logger.info(
        f"  Terms creation:    {timings['terms'] - timings['domains']:.2f}s  ({1000*(timings['terms']-timings['domains'])/num_terms:.1f} ms/op)"
    )
    logger.info(f"  Total:             {timings['terms'] - timings['start']:.2f}s\n")
    logger.info("[THROUGHPUT] Throughput test completed.")

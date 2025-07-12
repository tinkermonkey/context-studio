
# Ensure project root is on sys.path for imports
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import pytest
import time
import uuid
import psutil
from fastapi.testclient import TestClient
from database import models
from database.utils import init_db, get_session_local
from app import create_app

import logging

logger = logging.getLogger('perf_test')

# Set third-party libraries to WARNING to suppress their info/debug logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Optionally, set your own logger to INFO or DEBUG if you use logging
logging.basicConfig(level=logging.INFO)

# Use a temporary file for the test database
test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{test_db_path}"
engine = init_db(database_url=SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, skip_vec=False)
TestingSessionLocal = get_session_local(engine)

# Create a test app instance with test DB engine/session
app = create_app(engine=engine, session_local=TestingSessionLocal, skip_vec=False)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    yield
    os.close(test_db_fd)
    os.unlink(test_db_path)

@pytest.fixture
def client():
    return TestClient(app)

def create_layer(client, title=None):
    payload = {
        "title": title or f"Layer {uuid.uuid4()}",
        "definition": "Performance test layer."
    }
    response = client.post("/api/layers/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def create_domain(client, layer_id, title=None):
    payload = {
        "title": title or f"Domain {uuid.uuid4()}",
        "definition": "Performance test domain.",
        "layer_id": layer_id
    }
    response = client.post("/api/domains/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def create_term(client, domain, name=None):
    # domain is a dict with at least id, title, and layer_id
    payload = {
        "name": name or f"Term {uuid.uuid4()}",
        "title": name or f"Term {uuid.uuid4()}",
        "definition": "Performance test term.",
        "domain_id": domain["id"],
        "layer_id": domain["layer_id"]
    }
    response = client.post("/api/terms/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def create_relationship(client, source_term_id, target_term_id):
    payload = {
        "source_term_id": source_term_id,
        "target_term_id": target_term_id,
        "type": "related",
        "predicate": "related"
    }
    response = client.post("/api/term-relationships/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

def test_general_performance(client):
    mem_stats = {}
    def print_mem_usage(label):
        proc = psutil.Process(os.getpid())
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        db_size_mb = os.path.getsize(test_db_path) / (1024 * 1024)
        mem_stats[label] = (mem_mb, db_size_mb)
        logger.info(f"[PERF][MEM] {label}: Python RSS={mem_mb:.2f} MB, SQLite DB={db_size_mb:.2f} MB")


    # PRAGMA and SQLite tuning for vector search performance
    with engine.connect() as conn:
        from sqlalchemy import text
        conn.execute(text("PRAGMA cache_size = -65536;"))  # 64MB cache
        conn.execute(text("PRAGMA synchronous = OFF;"))
        conn.execute(text("PRAGMA journal_mode = WAL;"))
        conn.execute(text("PRAGMA temp_store = MEMORY;"))
    logger.info("[PERF][TUNE] Applied PRAGMA settings for SQLite performance.")

    print_mem_usage("Start")

    # Allow scale selection via environment variable or pytest param
    scale = os.environ.get("PERF_TEST_SCALE", "small").lower()
    # You can also override via pytest: pytest ... --scale=medium
    scale_override = getattr(pytest, 'perf_test_scale', None)
    if scale_override:
        scale = scale_override

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
        # New large: midway between medium and xlarge
        num_layers = 7
        num_domains_per_layer = 7
        num_terms_per_domain = 25
        num_relationships_per_term = 7
    elif scale == "xlarge":
        # Formerly 'large'
        num_layers = 10
        num_domains_per_layer = 10
        num_terms_per_domain = 50
        num_relationships_per_term = 10
    else:
        raise ValueError(f"Unknown PERF_TEST_SCALE: {scale}")

    logger.info(f"[PERF] Running performance test at scale: {scale}")

    layers = []
    domains = []
    terms = []

    start = time.time()
    logger.info(f"[PERF] Starting performance test: {num_layers} layers, {num_domains_per_layer} domains/layer, {num_terms_per_domain} terms/domain, {num_relationships_per_term} relationships/term")

    timings = {}
    timings['start'] = start

    # Create layers
    for i in range(num_layers):
        layer = create_layer(client, title=f"PerfLayer_{i}")
        layers.append(layer)
        if (i + 1) % 2 == 0 or (i + 1) == num_layers:
            logger.info(f"[PERF] Created {i + 1}/{num_layers} layers...")
    timings['layers'] = time.time()
    logger.info(f"[PERF] Created {num_layers} layers in {timings['layers'] - start:.2f}s")

    print_mem_usage("After layers")

    # Create domains for each layer
    domain_count = 0
    for li, layer in enumerate(layers):
        for j in range(num_domains_per_layer):
            domain = create_domain(client, layer_id=layer["id"], title=f"PerfDomain_{layer['id']}_{j}")
            domains.append(domain)
            domain_count += 1
            if (domain_count) % 10 == 0 or (domain_count) == num_layers * num_domains_per_layer:
                logger.info(f"[PERF] Created {domain_count}/{num_layers * num_domains_per_layer} domains...")
    timings['domains'] = time.time()
    logger.info(f"[PERF] Created {len(domains)} domains in {timings['domains'] - timings['layers']:.2f}s")

    print_mem_usage("After domains")

    # Create terms for each domain
    total_terms = num_domains_per_layer * num_layers * num_terms_per_domain
    terms_created = 0
    for di, domain in enumerate(domains):
        domain_terms = []
        for k in range(num_terms_per_domain):
            term = create_term(client, domain=domain, name=f"PerfTerm_{domain['id']}_{k}")
            domain_terms.append(term)
            terms_created += 1
            if terms_created % 1000 == 0 or terms_created == total_terms:
                logger.info(f"[PERF] Created {terms_created}/{total_terms} terms...")
        terms.append(domain_terms)
    timings['terms'] = time.time()
    logger.info(f"[PERF] Created {total_terms} terms in {timings['terms'] - timings['domains']:.2f}s")

    print_mem_usage("After terms")

    # Create relationships for each term (to other terms in the same domain)
    total_relationships = total_terms * num_relationships_per_term
    relationships_created = 0
    for domain_terms in terms:
        term_ids = [t["id"] for t in domain_terms]
        for idx, term in enumerate(domain_terms):
            for r in range(num_relationships_per_term):
                # Link to the next term (wrap around)
                target_idx = (idx + r + 1) % len(domain_terms)
                create_relationship(client, source_term_id=term["id"], target_term_id=term_ids[target_idx])
                relationships_created += 1
                if relationships_created % 1000 == 0 or relationships_created == total_relationships:
                    logger.info(f"[PERF] Created {relationships_created}/{total_relationships} relationships...")
    timings['relationships'] = time.time()
    logger.info(f"[PERF] Created {total_relationships} relationships in {timings['relationships'] - timings['terms']:.2f}s")

    print_mem_usage("After relationships")

    # Validate counts
    # Validate counts
    resp = client.get("/api/layers/?limit=100")
    assert resp.status_code == 200
    assert len(resp.json()) == num_layers
    timings['validation'] = time.time()
    logger.info(f"[PERF] Validation complete. {num_layers} layers found.")

    print_mem_usage("After validation")


    # Vector search performance for layers, domains, and terms
    # Number of searches is proportional to the number of terms (10%)
    n_layers = num_layers
    n_domains = num_layers * num_domains_per_layer
    n_terms = n_domains * num_terms_per_domain
    num_vector_searches = max(1, int(0.1 * n_terms))


    # Layers (use ANN if available, else fallback to normal search)
    layer_search_titles = [l['title'] for l in layers]
    layer_search_titles = (layer_search_titles * ((num_vector_searches // len(layer_search_titles)) + 1))[:num_vector_searches]
    search_times = []
    total_results = 0
    last_log = 0
    for i, search_title in enumerate(layer_search_titles, 1):
        search_payload = {"title": search_title, "limit": 10}
        search_start = time.time()
        resp = client.post("/api/layers/find", json=search_payload)
        elapsed = time.time() - search_start
        assert resp.status_code == 200
        results = resp.json()
        assert any(l['title'] == search_title for l in results)
        search_times.append(elapsed)
        total_results += len(results)
        # Incremental logging every 10%
        percent = int((i / num_vector_searches) * 100)
        if percent // 10 > last_log:
            ms_per_search = (sum(search_times) / len(search_times)) * 1000 if search_times else 0
            logger.info(f"[PERF] [Layers] Vector search progress: {percent}% ({i}/{num_vector_searches}), avg {ms_per_search:.2f} ms/search so far")
            last_log = percent // 10
    avg_search_time = sum(search_times) / len(search_times)
    timings['vector_search_layers'] = time.time()
    logger.info(f"[PERF] [Layers] Ran {num_vector_searches} vector searches, avg {avg_search_time:.4f}s/search, total results: {total_results}")

    # Domains (use ANN if available, else fallback to normal search)
    domain_search_titles = [d['title'] for d in domains]
    domain_search_titles = (domain_search_titles * ((num_vector_searches // len(domain_search_titles)) + 1))[:num_vector_searches]
    domain_search_times = []
    domain_total_results = 0
    last_log = 0
    for i, search_title in enumerate(domain_search_titles, 1):
        search_payload = {"title": search_title, "limit": 10}
        search_start = time.time()
        resp = client.post("/api/domains/find", json=search_payload)
        elapsed = time.time() - search_start
        assert resp.status_code == 200
        results = resp.json()
        assert any(d['title'] == search_title for d in results)
        domain_search_times.append(elapsed)
        domain_total_results += len(results)
        # Incremental logging every 10%
        percent = int((i / num_vector_searches) * 100)
        if percent // 10 > last_log:
            ms_per_search = (sum(domain_search_times) / len(domain_search_times)) * 1000 if domain_search_times else 0
            logger.info(f"[PERF] [Domains] Vector search progress: {percent}% ({i}/{num_vector_searches}), avg {ms_per_search:.2f} ms/search so far")
            last_log = percent // 10
    avg_domain_search_time = sum(domain_search_times) / len(domain_search_times)
    timings['vector_search_domains'] = time.time()
    logger.info(f"[PERF] [Domains] Ran {num_vector_searches} vector searches, avg {avg_domain_search_time:.4f}s/search, total results: {domain_total_results}")

    # Terms (use ANN if available, else fallback to normal search)
    # Flatten all terms into a single list
    all_terms = [t for domain_terms in terms for t in domain_terms]
    term_search_titles = [t['title'] for t in all_terms]
    term_search_titles = (term_search_titles * ((num_vector_searches // len(term_search_titles)) + 1))[:num_vector_searches]
    term_search_times = []
    term_total_results = 0
    last_log = 0
    for i, search_title in enumerate(term_search_titles, 1):
        search_payload = {"title": search_title, "limit": 10}
        search_start = time.time()
        resp = client.post("/api/terms/find", json=search_payload)
        elapsed = time.time() - search_start
        assert resp.status_code == 200
        results = resp.json()
        assert any(t['title'] == search_title for t in results)
        term_search_times.append(elapsed)
        term_total_results += len(results)
        # Incremental logging every 10%
        percent = int((i / num_vector_searches) * 100)
        if percent // 10 > last_log:
            ms_per_search = (sum(term_search_times) / len(term_search_times)) * 1000 if term_search_times else 0
            logger.info(f"[PERF] [Terms] Vector search progress: {percent}% ({i}/{num_vector_searches}), avg {ms_per_search:.2f} ms/search so far")
            last_log = percent // 10
    avg_term_search_time = sum(term_search_times) / len(term_search_times)
    timings['vector_search_terms'] = time.time()
    logger.info(f"[PERF] [Terms] Ran {num_vector_searches} vector searches, avg {avg_term_search_time:.4f}s/search, total results: {term_total_results}")


    print_mem_usage("After vector search")

    # Memory usage summary
    initial_mem, initial_db = mem_stats.get("Start", (None, None))
    final_mem, final_db = mem_stats.get("After vector search", (None, None))
    if initial_mem is not None and final_mem is not None:
        logger.info(f"[PERF][MEM][SUMMARY] Python RSS delta: {final_mem - initial_mem:.2f} MB (from {initial_mem:.2f} MB to {final_mem:.2f} MB)")
    if initial_db is not None and final_db is not None:
        logger.info(f"[PERF][MEM][SUMMARY] SQLite DB size delta: {final_db - initial_db:.2f} MB (from {initial_db:.2f} MB to {final_db:.2f} MB)")

    # Performance summary with rates
    n_layers = num_layers
    n_domains = num_layers * num_domains_per_layer
    n_terms = n_domains * num_terms_per_domain
    n_relationships = n_terms * num_relationships_per_term
    logger.info("\n[PERF] Performance Summary:")
    logger.info(f"  Layers creation:         {timings['layers'] - timings['start']:.2f}s  ({1000*(timings['layers']-timings['start'])/n_layers:.1f} ms/op)")
    logger.info(f"  Domains creation:        {timings['domains'] - timings['layers']:.2f}s  ({1000*(timings['domains']-timings['layers'])/n_domains:.1f} ms/op)")
    logger.info(f"  Terms creation:          {timings['terms'] - timings['domains']:.2f}s  ({1000*(timings['terms']-timings['domains'])/n_terms:.1f} ms/op)")
    logger.info(f"  Relationships creation:  {timings['relationships'] - timings['terms']:.2f}s  ({1000*(timings['relationships']-timings['terms'])/n_relationships:.1f} ms/op)")
    logger.info(f"  Validation:              {timings['validation'] - timings['relationships']:.2f}s")
    logger.info(f"  Vector search (layers):  {timings['vector_search_layers'] - timings['validation']:.2f}s  (avg {avg_search_time*1000:.2f} ms/search, {num_vector_searches} searches)")
    logger.info(f"  Vector search (domains): {timings['vector_search_domains'] - timings['vector_search_layers']:.2f}s  (avg {avg_domain_search_time*1000:.2f} ms/search, {num_vector_searches} searches)")
    logger.info(f"  Vector search (terms):   {timings['vector_search_terms'] - timings['vector_search_domains']:.2f}s  (avg {avg_term_search_time*1000:.2f} ms/search, {len(term_search_titles)} searches)")
    logger.info(f"  Total:                   {timings['vector_search_terms'] - timings['start']:.2f}s\n")
    logger.info("[PERF] Performance test completed.")

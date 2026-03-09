# mypy: ignore-errors
import spacy
import time
import requests
from reference_api_buddy.core.proxy import CachingProxy

# os.environ['HTTP_PROXY'] = 'http://localhost:8080'

config = {
    "logging": {
        "level": "DEBUG",
        # "enable_console": True,
        # "enable_file": True,
        # "file_path": LOG_FILE,
        # "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        # "date_format": "%Y-%m-%d %H:%M:%S",
    },
    "server": {
        "host": "127.0.0.1",
        "port": 18080,
    },
    "domain_mappings": {
        # Intercept requests to /dbpedia_spotlight and map to api.dbpedia-spotlight.org
        "dbpedia_spotlight": {"upstream": "https://api.dbpedia-spotlight.org/en/"}
    },
    # "cache": {"database_path": "smoke_tests/cache.db", "max_cache_response_size": 10485760},
    "security": {},
    "throttling": {},
    "callbacks": {},
}

# Start the proxy in a background thread
proxy = CachingProxy(config)
proxy.start(blocking=False)

# Give the server a moment to start
print("Waiting for proxy to start...")
time.sleep(1)

if False:
    # Target endpoint: /dbpedia_spotlight/annotate (maps to https://api.dbpedia-spotlight.org/en/annotate)
    proxy_url = "http://127.0.0.1:18080/dbpedia_spotlight/annotate"

    payload = {"text": "A sentence about apple sauce."}

    headers = {"accept": "application/json"}

    print("Making first request (should be a cache miss)...")
    start1 = time.time()
    resp1 = requests.post(proxy_url, data=payload, headers=headers)
    duration1 = time.time() - start1
    print(
        f"First request status: {resp1.status_code}, duration: {duration1:.3f}s, body: {resp1.text}..."
    )

if True:
    nlp = spacy.blank("en")
    nlp.add_pipe(
        "dbpedia_spotlight",
        config={"dbpedia_rest_endpoint": "http://127.0.0.1:18080/dbpedia_spotlight"},
    )

    doc = nlp("A sentence about apple sauce.")
    print(
        [
            (ent.text, ent.kb_id_, ent._.dbpedia_raw_result["@similarityScore"])
            for ent in doc.ents
        ]
    )

    print("Spans: ", doc.spans["dbpedia_spotlight"])

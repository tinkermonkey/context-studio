import spacy
import concepcy
import time
import requests

from reference_api_buddy.core.proxy import CachingProxy

config = {
    "logging": {
        "level": "INFO",
        #"enable_console": True,
        #"enable_file": True,
        #"file_path": LOG_FILE,
        #"format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        #"date_format": "%Y-%m-%d %H:%M:%S",
    },
    "server": {
        "host": "127.0.0.1",
        "port": 18080,
    },
    "domain_mappings": {
        "conceptnet": {
            "upstream": "https://api.conceptnet.io"
        }
    },
    "cache": {
        "database_path": "cache.db"
    },
}

proxy = CachingProxy(config)
proxy.start(blocking=False)

# Give the server a moment to start
print("Waiting for proxy to start...")
time.sleep(1)

# Set proxy BEFORE importing any libraries
# os.environ['HTTP_PROXY'] = 'http://localhost:8080'
# os.environ['HTTPS_PROXY'] = 'http://localhost:8080'

# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# ssl._create_default_https_context = ssl._create_unverified_context


def make_request(url, request_id):
    """Make a single request and return the result."""
    try:
        print(f"Request {request_id}: Starting...")
        response = requests.get(url, timeout=10)
        
        # Try to parse the response as JSON to replicate the original issue
        try:
            response_json = response.json()
            json_valid = True
            json_keys = list(response_json.keys()) if isinstance(response_json, dict) else "not_dict"
        except (ValueError, TypeError) as json_error:
            json_valid = False
            json_keys = f"JSON_PARSE_ERROR: {json_error}"
            print(f"Request {request_id}: JSON parse error - {json_error}")
        
        print(f"Request {request_id}: Status {response.status_code}, Length: {len(response.text)}, JSON Valid: {json_valid}, Keys: {json_keys}")
        return response.status_code, len(response.text), json_valid, json_keys, None
    except Exception as e:
        print(f"Request {request_id}: ERROR - {e}")
        return None, None, False, None, str(e)


def main():
    print("✅ concepCy imported successfully!")

    # Make a request to verify the proxy is functioning
    make_request("http://127.0.0.1:18080/conceptnet/query?node=/c/en/email&other=/c/en", 1)

    # Create a new spaCy pipeline
    nlp = spacy.load("en_core_web_sm")

    predicates = [
        "RelatedTo",
        "FormOf",
        "IsA",
        "PartOf",
        "HasA",
        "UsedFor",
        "CapableOf",
        "AtLocation",
        "Causes",
        "HasSubevent",
        "HasFirstSubevent",
        "HasLastSubevent",
        "HasPrerequisite",
        "HasProperty",
        "MotivatedByGoal",
        "ObstructedBy",
        "Desires",
        "CreatedBy",
        "Synonym",
        "Antonym",
        "DistinctFrom",
        "DerivedFrom",
        "SymbolOf",
        "DefinedAs",
        "MannerOf",
        "LocatedNear",
        "HasContext",
        "SimilarTo",
        "EtymologicallyRelatedTo",
        "EtymologicallyDerivedFrom",
        "CausesDesire",
        "MadeOf",
        "ReceivesAction",
        "ExternalURL",
    ]

    nlp.add_pipe(
        "concepcy",
        config={
            "url": "http://127.0.0.1:18080/conceptnet/query?node=/c/{lang}/{word}&other=/c/{lang}",
            "relations_of_interest": predicates,
            "filter_missing_text": True,
            "filter_edge_weight": 2,
        },
    )

    doc = nlp("email is a great way to communicate.")

    # Access all the "RelatedTo" relations from the Doc
    if False:
        print("--- All the 'RelatedTo' relations from the Doc ---")
        for word, relations in doc._.relatedto.items():
            print(f"Word: '{word}'\n{relations}")

    # Access the "RelatedTo" relations word by word
    if False:
        print("--- The 'RelatedTo' relations word by word ---")
        for token in doc:
            print(f"Word: '{token}'\n{token._.relatedto}\n")

    # See what other relations are available under doc._
    print("--- Other relations available ---")
    for attr in dir(doc._):
        if not attr.startswith("_"):
            print(f" - {attr}")
            print(getattr(doc._, attr))

    # dbpedia_raw_result
    if hasattr(doc._, "dbpedia_raw_result") and doc._.dbpedia_raw_result:
        print(f"DBpedia raw result: {doc._.dbpedia_raw_result}")

    # instanceof
    if hasattr(doc._, "instanceof") and doc._.instanceof:
        print(f"Instanceof: {doc._.instanceof}")

    # run the nlp again to confirm the caching
    doc = nlp("email is a great way to communicate.")

    print("Second pass:")
    for token in doc:
        print(f"Word: '{token}'\n{token._.relatedto}\n")

if __name__ == "__main__":
    main()

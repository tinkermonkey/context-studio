import sys
import os
import json

# Disable proxy for debugging to avoid proxy conflicts
use_proxy = False

if use_proxy:
    import urllib3
    import ssl

    # Set proxy BEFORE importing any libraries
    os.environ['HTTP_PROXY'] = 'http://localhost:8080'
    os.environ['HTTPS_PROXY'] = 'http://localhost:8080'
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['CURL_CA_BUNDLE'] = ''

    import requests
    old_request = requests.Session.request
    def new_request(self, *args, **kwargs):
        kwargs['verify'] = False
        return old_request(self, *args, **kwargs)
    requests.Session.request = new_request
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    ssl._create_default_https_context = ssl._create_unverified_context

# Add project root to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"Adding {parent_dir} to sys.path")
sys.path.insert(0, parent_dir)

from nlp.pipeline import get_pipeline  # noqa: E402
from nlp.processors import process_nlp_result  # noqa: E402

def main():
    if len(sys.argv) < 2:
        print("Usage: python utils/nlp_debug.py '<your text>'")
        sys.exit(1)
    text = sys.argv[1]
    pipeline = get_pipeline().get_nlp()
    if pipeline is None:
        print("NLP pipeline is not initialized.")
        sys.exit(2)
    doc = pipeline(text)
    result = process_nlp_result(text, doc)
    # Convert Pydantic model to dict (use model_dump for Pydantic v2)
    if hasattr(result, 'model_dump'):
        result_dict = result.model_dump()
    elif hasattr(result, 'dict'):
        result_dict = result.model_dump()
    else:
        result_dict = result
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    output_path = os.path.join(logs_dir, "debug.json")
    with open(output_path, "w") as f:
        json.dump(result_dict, f, indent=2)
    print(f"NLP analysis saved to {output_path}")

if __name__ == "__main__":
    main()

import sys
import os
import json

# Add project root to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"Adding {parent_dir} to sys.path")
sys.path.insert(0, parent_dir)
from nlp.pipeline import get_pipeline
from nlp.processors import process_nlp_result

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
    # Convert Pydantic model to dict
    result_dict = result.dict() if hasattr(result, 'dict') else result
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    output_path = os.path.join(logs_dir, "debug.json")
    with open(output_path, "w") as f:
        json.dump(result_dict, f, indent=2)
    print(f"NLP analysis saved to {output_path}")

if __name__ == "__main__":
    main()

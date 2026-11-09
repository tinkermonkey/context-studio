"""
The library of example paragraphs for trying the extraction pipelines (#1315).

The examples are curated and ship with the app in
``datafiles/extraction_examples.json``; they are read once at startup and
served read-only.
"""

import json
from pathlib import Path

from adapters.web.schemas.pipelines import ExtractionExampleResponse

EXTRACTION_EXAMPLES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "datafiles" / "extraction_examples.json"
)


def load_extraction_examples(
    path: Path = EXTRACTION_EXAMPLES_PATH,
) -> list[ExtractionExampleResponse]:
    """
    Read and validate the example library.

    Args:
        path: The examples JSON file ({"examples": [...]})

    Returns:
        The examples in file order

    Raises:
        ValueError: If the file is malformed, an example is invalid, or two share an id
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    examples = [ExtractionExampleResponse.model_validate(item) for item in data["examples"]]
    ids = [e.id for e in examples]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"Duplicate extraction example id(s): {', '.join(duplicates)}")
    return examples

#!/usr/bin/env python3
"""Generate HTTP cassettes for grounding quality test fixtures.

Creates a single cassette file with HTTP interactions for all grounding
fixtures across DBpedia, ConceptNet, and Wikidata sources (schema.org is offline).

Reads expected.json files to extract the correct URIs for matching.
"""

import json
import sys
from pathlib import Path


def load_expected_uris(fixture_scenario: str) -> dict[str, str]:
    """Load expected URIs from expected.json file, indexed by source.

    Raises FileNotFoundError if expected.json is missing, to prevent
    generating cassettes with fabricated URIs.
    """
    fixtures_dir = (
        Path(__file__).parent.parent / "tests/integration/fixtures/pipelines/schema_node_grounding"
    )
    expected_file = fixtures_dir / fixture_scenario / "expected.json"

    if not expected_file.exists():
        raise FileNotFoundError(
            f"Expected fixture data not found: {expected_file}. "
            f"Cannot generate cassette with accurate URIs. "
            f"Ensure the fixture directory has expected.json with expected_external_references."
        )

    uris_by_source = {}
    with open(expected_file) as f:
        data = json.load(f)
        for ref in data.get("expected_external_references", []):
            source = ref.get("source")
            uri = ref.get("uri")
            if source and uri:
                uris_by_source[source] = uri

    return uris_by_source


def generate_dbpedia_response(label: str, uri: str | None = None) -> str:
    """Generate a DBpedia response matching the adapter's expected format."""
    if uri is None:
        uri = f"http://dbpedia.org/resource/{label.replace(' ', '_')}"

    response = {
        "results": [
            {
                "uri": uri,
                "label": label,
                "description": f"DBpedia entry for {label}",
            }
        ]
    }
    return json.dumps(response)


def generate_conceptnet_response(label: str, uri: str | None = None) -> str:
    """Generate a ConceptNet response matching the adapter's expected format."""
    if uri is None:
        uri = f"http://conceptnet.io/c/en/{label.lower().replace(' ', '_')}"

    response = {
        "edges": [
            {
                "start": {
                    "@id": uri,
                    "label": label,
                },
                "rel": {"label": "related_to"},
                "end": {"@id": "/c/en/related", "label": "related"},
            }
        ],
        "@context": {},
        "@id": uri,
    }
    return json.dumps(response)


def generate_wikidata_response(
    label: str, entity_id: str | None = None, uri: str | None = None
) -> str:
    """Generate a Wikidata response matching the adapter's expected format."""
    if uri:
        # Extract entity ID from URI
        entity_id = uri.split("/")[-1]
    elif entity_id is None:
        entity_id = f"Q{1000 + hash(label) % 10000}"

    response = {
        "search": [
            {
                "id": entity_id,
                "label": label,
                "description": f"Wikidata item for {label}",
                "url": f"https://www.wikidata.org/wiki/{entity_id}",
            }
        ]
    }
    return json.dumps(response)


def main():
    """Generate HTTP cassettes for grounding quality test fixtures.

    Fails loudly if fixture data is missing to prevent generating
    cassettes with fabricated URIs.
    """
    try:
        cassette_path = (
            Path(__file__).parent.parent
            / "tests/integration/pipelines/schema_node_grounding"
            / "_cassettes"
            / "test_quality_schema_node_grounding"
            / "test_quality_metrics_computation_all_fixtures.json"
        )

        cassette_path.parent.mkdir(parents=True, exist_ok=True)

        fixtures_dir = (
            Path(__file__).parent.parent
            / "tests/integration/fixtures/pipelines/schema_node_grounding"
        )

        # Get all fixture scenarios
        fixture_scenarios = sorted(
            [
                d.name
                for d in fixtures_dir.iterdir()
                if d.is_dir() and (d / "input.json").exists() and d.name != ".gitkeep"
            ]
        )

        if not fixture_scenarios:
            raise FileNotFoundError(
                f"No grounding fixtures found in {fixtures_dir}. "
                f"Expected directories with input.json files."
            )

        interactions = []
        failed_fixtures = []

        # Generate interactions for each fixture
        for scenario in fixture_scenarios:
            try:
                # Load expected URIs for this fixture - may raise FileNotFoundError
                uris_by_source = load_expected_uris(scenario)

                # Load the input fixture to get the label
                input_file = fixtures_dir / scenario / "input.json"
                with open(input_file) as f:
                    input_data = json.load(f)
                    label = input_data.get("node_label", scenario.title())

                # DBpedia interaction
                dbpedia_uri = uris_by_source.get("DBpedia")
                interactions.append(
                    {
                        "request": {
                            "method": "GET",
                            "url": (
                                f"https://lookup.dbpedia.org/api/search"
                                f"?query={label}&format=json&maxResults=10"
                            ),
                            "headers": {},
                            "body": None,
                        },
                        "response": {
                            "status_code": 200,
                            "headers": {"content-type": "application/json"},
                            "body": generate_dbpedia_response(label, dbpedia_uri),
                        },
                    }
                )

                # ConceptNet interaction
                conceptnet_uri = uris_by_source.get("ConceptNet")
                label_slug = label.lower().replace(" ", "_")
                interactions.append(
                    {
                        "request": {
                            "method": "GET",
                            "url": f"https://api.conceptnet.io/c/en/{label_slug}" f"?limit=10",
                            "headers": {},
                            "body": None,
                        },
                        "response": {
                            "status_code": 200,
                            "headers": {"content-type": "application/json"},
                            "body": generate_conceptnet_response(label, conceptnet_uri),
                        },
                    }
                )

                # Wikidata interaction
                wikidata_uri = uris_by_source.get("Wikidata")
                interactions.append(
                    {
                        "request": {
                            "method": "GET",
                            "url": (
                                f"https://www.wikidata.org/w/api.php"
                                f"?action=wbsearchentities&search={label}"
                                f"&language=en&format=json&limit=10"
                            ),
                            "headers": {},
                            "body": None,
                        },
                        "response": {
                            "status_code": 200,
                            "headers": {"content-type": "application/json"},
                            "body": generate_wikidata_response(label, uri=wikidata_uri),
                        },
                    }
                )
                print(f"  ✓ {scenario}")

            except FileNotFoundError as e:
                print(f"  ✗ {scenario}: {e}")
                failed_fixtures.append(scenario)

        if failed_fixtures:
            num_failed = len(failed_fixtures)
            raise RuntimeError(
                f"Failed to generate cassettes for {num_failed} fixture(s): " f"{failed_fixtures}"
            )

        # Write cassette
        cassette = {"interactions": interactions}
        with open(cassette_path, "w") as f:
            json.dump(cassette, f, indent=2)

        print(f"\n✓ Generated cassette with {len(interactions)} interactions at {cassette_path}")

    except (FileNotFoundError, RuntimeError) as e:
        print(f"\n❌ Cassette generation FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during cassette generation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

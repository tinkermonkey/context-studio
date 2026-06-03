# Schema Node Grounding HTTP Cassettes

This directory contains HTTP cassettes (pre-recorded HTTP request/response pairs) for the schema node grounding quality tests. Cassettes enable deterministic testing without external network dependencies.

## Cassette Structure

Each subdirectory contains cassettes for a specific grounding source:

- `dbpedia/` - DBpedia reference source HTTP responses
- `conceptnet/` - ConceptNet reference source HTTP responses  
- `wikidata/` - Wikidata reference source HTTP responses

## Cassette Format

Cassettes are stored as YAML files in a format compatible with respx (httpx mocking library) and other HTTP recording tools. Each cassette contains:

- `interactions`: Array of recorded HTTP request/response pairs
- `request`: The HTTP request (method, URI, headers)
- `response`: The HTTP response (status code, headers, body)
- `version`: Cassette format version (1)

## Recording New Cassettes

To record a new cassette for a test scenario:

1. Enable cassette recording mode in the test configuration
2. Run tests against live services (DBpedia, ConceptNet, Wikidata)
3. Cassettes are automatically saved to the appropriate source subdirectory
4. Commit cassette files alongside test code

Example cassette filename: `{source}/{scenario}.yaml`

For the "person" scenario and DBpedia source, the cassette would be saved as `dbpedia/person.yaml`.

## Using Cassettes in Tests

Tests use cassettes by:

1. Checking if a cassette exists for the scenario
2. If it exists, mocking HTTP calls to use recorded responses
3. If it doesn't exist (in development/recording mode), making live calls and recording responses
4. Committing cassettes ensures future test runs use pre-recorded data

Schema.org requires no HTTP cassette because it is a static schema served locally.

## Cassettes Committed

The following cassettes are committed and ready for use:

- `dbpedia/person.yaml` - DBpedia Person reference
- `conceptnet/person.yaml` - ConceptNet Person reference
- `wikidata/person.yaml` - Wikidata Person reference

Additional cassettes can be recorded as the test corpus expands.

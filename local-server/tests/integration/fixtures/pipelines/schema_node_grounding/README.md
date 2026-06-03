# Schema Node Grounding Quality Suite Fixtures

This directory contains the comprehensive fixture corpus for the schema node grounding pipeline quality suite. 

## Structure

Each quality scenario is organized in its own directory with three required files:

- **`input.json`**: Pipeline input specifying the node to be grounded
- **`expected.json`**: Hand-labeled ground truth containing expected external references
- **`distractors.json`**: Plausible-but-wrong candidates (3-5 per source) for ranking evaluation

## Scenario Naming

Scenarios use descriptive names based on the domain and concept being tested:

- Biology: `animal`, `plant`, `cell`, `protein`, `dna`, `bacteria`, `virus`
- Chemistry: `chemical_element`, `chemical_compound`, `atom`, `energy`
- Physics: `motion`, `space`, `time`
- Technology: `software`, `network`, `algorithm`, `database`
- Social/Humanities: `person`, `organization`, `location`, `event`, `artist`, `university`, `government`, `language`, `book`, `sport`, `music`
- Geography: `river`, `mountain`, `ocean`
- Astronomy: `star`
- Medicine: `disease`
- Urban: `building`, `vehicle`, `food`, `color`

**Total: 38 quality scenarios (exceeds 30-class requirement)**

## Ground Truth Attribution

Each `expected.json` includes the rationale for why each reference was selected:

- **URIs from DBpedia**: Primary source for linked data entities; well-established Wikipedia-linked resources
- **URIs from Wikidata**: Authoritative knowledge base items (Qxxxx identifiers); multilingual coverage
- **URIs from ConceptNet**: Semantic networks representing conceptual relationships
- **URIs from schema.org**: Schema markup definitions; standardized type definitions for web data

References are hand-labeled based on:
1. Direct name match (e.g., "Person" → schema.org/Person)
2. Semantic equivalence (e.g., "DNA" is an instance of "biological molecule")
3. Standard reference data availability (DBpedia for articles, Wikidata for entities, ConceptNet for semantic relations)

## Distractor Strategy

Each scenario includes 3-5 "plausible-but-wrong" candidates per source:

- **Sibling concepts**: Related but incorrect (e.g., "House" as distractor for "Person")
- **Near-homonyms**: Similar names with different meanings (e.g., "Individual" for "Person")
- **Type confusion**: Confusing semantic types (e.g., "Organism" for "Person")
- **Category error**: Wrong domain entirely (e.g., "Chemical Element" for "Person")

Distractors enable evaluation of ranking precision beyond simple recall. The quality suite requires:
- **top1_precision ≥ 0.50**: First result matches ground truth ≥50% of the time
- **top3_precision ≥ 0.70**: Top-3 results contain a match ≥70% of the time
- **mrr ≥ 0.60**: Mean reciprocal rank of first correct match ≥0.60

## Fixture Format

### input.json
```json
{
  "node_label": "Person",
  "node_type": "Class",
  "sources": ["DBpedia", "ConceptNet", "Wikidata", "schema.org"]
}
```

### expected.json
```json
{
  "expected_external_references": [
    {
      "uri": "http://dbpedia.org/resource/Person",
      "source": "DBpedia",
      "rationale": "Core concept for human beings"
    },
    {
      "uri": "http://www.wikidata.org/entity/Q5",
      "source": "Wikidata",
      "rationale": "Wikidata: human"
    },
    {
      "uri": "https://schema.org/Person",
      "source": "schema.org",
      "rationale": "schema.org definition"
    },
    {
      "uri": "http://conceptnet.io/c/en/person",
      "source": "ConceptNet",
      "rationale": "ConceptNet person concept"
    }
  ]
}
```

### distractors.json
```json
{
  "DBpedia": [
    "http://dbpedia.org/resource/Individual",
    "http://dbpedia.org/resource/Human",
    "http://dbpedia.org/resource/Man"
  ],
  "ConceptNet": [
    "http://conceptnet.io/c/en/human",
    "http://conceptnet.io/c/en/individual"
  ],
  "Wikidata": [
    "http://www.wikidata.org/entity/Q43229",
    "http://www.wikidata.org/entity/Q7725634"
  ],
  "schema.org": [
    "https://schema.org/Agent",
    "https://schema.org/Thing"
  ]
}
```

## HTTP Cassettes

The quality suite runs in **recorded mode** (with HTTP cassettes) to ensure:
- Deterministic, repeatable test execution
- Zero network calls in CI/CD environments
- Consistent results independent of external service availability

Cassettes are stored in `/tests/fixtures/cassettes/schema_node_grounding/` with the naming pattern:
- `{source}_{scenario}.json` for each source (e.g., `dbpedia_person.json`)
- Cassettes capture actual HTTP responses from DBpedia, ConceptNet, and Wikidata
- schema.org requires no cassette (offline data)

To refresh cassettes (requires network access):
```bash
pytest --refresh-cassettes tests/integration/pipelines/schema_node_grounding/test_quality_schema_node_grounding.py
```

## Quality Metric Computation

For each scenario, the suite computes:

1. **top1_precision**: Binary flag (0 or 1) if the top-ranked candidate matches ground truth
2. **top3_precision**: Binary flag (0 or 1) if any of top-3 candidates match ground truth
3. **mrr**: Mean reciprocal rank = 1 / (rank of first correct match), or 0 if no match in top-10
4. **distractor_precision**: Ratio of top-ranked results that are NOT distractors

Metrics are aggregated and reported as JSONL rows with per-scenario and aggregate statistics.

## Extending the Corpus

To add new scenarios:

1. Choose a domain and concept name (e.g., `enzyme` for biochemistry)
2. Create directory: `tests/integration/fixtures/pipelines/schema_node_grounding/enzyme/`
3. Create `input.json` with node_label and sources
4. Create `expected.json` with 1-4 expected URIs from the available sources
5. Create `distractors.json` with 3-5 distractors per source (minimum 1 per scenario)

Example:
```bash
mkdir -p tests/integration/fixtures/pipelines/schema_node_grounding/enzyme
cat > enzyme/input.json << 'EOF'
{
  "node_label": "Enzyme",
  "node_type": "Class",
  "sources": ["DBpedia", "ConceptNet", "Wikidata", "schema.org"]
}
EOF
```

Then run the quality suite to see if your new fixture achieves the metric floors.

# Connection Refinement Quality Fixtures

Corpus contains ≥20 curated fixture scenarios covering operations: `add`, `remove`, `modify`.

Measured on per-operation delta-set overlap: (operation, subject_class, predicate, object_class) tuples.

## Fixture Schema

Each fixture scenario directory contains:

### input.json
- `scope_id`: Unique identifier for the scope class being refined
- `scope_identifier`: Slug-style identifier for the scope class
- `scope_title`: Display title of the scope class
- `scope_description`: Description of the scope class
- `candidate_classes`: Array of candidate classes available for connection
  - `id`: Class identifier
  - `identifier`: Slug identifier
  - `title`: Display title
- `before_relationships`: Array of existing relationships in scope
  - `subject_id`: Source class ID
  - `object_id`: Target class ID
  - `predicate`: Relationship type
- `candidates`: Array of candidate relationships (may be empty)
- `is_empty_delta`: Boolean flag; if true, pipeline should propose no deltas
- `model`: LLM model to use
- `temperature`: LLM temperature parameter

### expected.json
- `status`: Expected pipeline status (e.g., "completed")
- `result.deltas`: Array of expected deltas
  - `operation`: "add" | "remove" | "modify"
  - `subject`: Source class label
  - `predicate`: Relationship type
  - `object`: Target class label
  - `confidence`: Expected confidence (0.0-1.0)

## Operation Coverage

This corpus includes:
- **≥1 fixture with `add` operations**: Testing creation of new relationships
- **≥1 fixture with `remove` operations**: Testing deletion of stale relationships
- **≥1 fixture with `modify` operations**: Testing tracking of relationship modifications (primary regression target for silent-drop bug)
- **≥3 empty-delta fixtures**: Testing pipelines's ability to recognize when no changes are needed

## Metric Floors

Validated per-operation on (operation, subject_class, predicate, object_class) tuples:
- **delta_f1** ≥ 0.40: Overall F1 on union of all delta types
- **add_recall** ≥ 0.30: Recall for add operations (for fixtures with expected adds)
- **remove_recall** ≥ 0.30: Recall for remove operations (for fixtures with expected removes)
- **modify_recall** ≥ 0.30: Recall for modify operations (for fixtures with expected modifies)

## Regression Test: Silent-Drop Bug

Test `test_connection_refinement_apply_roundtrip_with_modify` explicitly validates that:
1. **add** operations create new relationships in the ontology
2. **remove** operations delete existing relationships
3. **modify** operations are properly tracked (not silently dropped)

This is the primary regression target, addressing the historical issue where modify operations were tracked in counts but not in ontology state.

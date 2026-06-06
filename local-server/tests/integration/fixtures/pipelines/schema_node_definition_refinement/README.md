# Definition Refinement Quality Fixtures

Pinned Embedding Model: **all-MiniLM-L12-v2** (SentenceTransformer)

This corpus contains ≥20 curated fixture scenarios covering:
- **Clarification**: Making vague definitions more precise (e.g., "A pattern" → "A design pattern for...")
- **Scope Narrowing**: Specializing overly-broad definitions (e.g., "A software concept" → "An architectural style...")
- **Terminology Alignment**: Using standard or domain-specific terms consistently

## Fixture Schema

Each fixture scenario directory contains:

### input.json
- `node_id`: Unique identifier for the class being refined
- `identifier`: Slug-style identifier for the class
- `title`: Display title of the class
- `current_description`: The existing (possibly thin or vague) description
- `expected_description`: Hand-labeled target description for evaluation
- `is_no_regress`: Boolean flag; if true, the current description is already good (cosine ≥ 0.85), and the pipeline must either match it closely or abstain
- `model`: LLM model to use
- `temperature`: LLM temperature parameter

### expected.json
- `status`: Expected pipeline status (e.g., "completed")
- `result.expected_description`: The target description for embedding similarity comparison

## No-Regress Fixtures

Fixtures marked `is_no_regress: true` test the pipeline's ability to avoid degrading already-good descriptions. The test asserts that:
- Either all candidates have cosine ≥ 0.85 to the current description, OR
- The pipeline proposes no candidates (abstains)

This ensures the pipeline is conservative and doesn't risk replacing a decent description with a worse one.

## Metric Floors

Validated across the full corpus:
- **mean_cosine** ≥ 0.75: Average embedding similarity between best candidate and expected
- **pct_above_060** ≥ 80%: At least 80% of (non-no-regress) fixtures achieve cosine ≥ 0.60
- **no_regress_rate** ≥ 90%: At least 90% of no-regress fixtures pass (maintain ≥ 0.85 or abstain)

# Arxiv Researcher Profile Fixture

**Source:** Synthetic academic-profile fixture (placeholder subject 'John Doe'; not a real person or paper) originally bundled as an unused NLP-pipeline test fixture.
**Promoted from:** `fixture_paper_1.json` (arxiv-domain fixture unused by any test,
promoted into a full quality-corpus scenario per
`documentation/karpathy_loop_design.md` §3.3)
**License:** Educational use, fair use for testing
**Curator:** Claude (LLM-drafted ground truth, auto-promoted — see
`../NEEDS_HUMAN_REVIEW.md`; NOT yet human-reviewed)

## Overview
Fixture tests extraction of individuals/relationships from an arxiv-style
technical abstract — a distinct domain from the software-architecture-concept
scenarios that make up the rest of this corpus.

## Annotation Notes
- Ground-truth `expected.json` triples were drafted by an automated agent
  directly from `text`, following the same subject/predicate/object
  conventions as the hand-labeled scenarios in this directory.
- Includes one `excluded` negation/near-miss triple with a rationale, and one
  templated low-confidence distractor triple, matching the convention used by
  the other scenarios in this corpus.
- **This fixture has not been human-reviewed.** Do not treat its
  `expected.json` as authoritative ground truth for accept/reject decisions
  until a human has skimmed it (see `../NEEDS_HUMAN_REVIEW.md`).

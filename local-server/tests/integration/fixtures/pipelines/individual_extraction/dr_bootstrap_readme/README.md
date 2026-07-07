# DR Bootstrap Fixture: README.md

**Source:** `documentation_robotics_viewer`'s own dogfooded DR model
(`documentation-robotics/model/`), a real, independently-produced model.
**Wave:** 1 -- bootstrap corpus
(`documentation/karpathy_loop_dr_ontology_design.md` §5)
**Ontology:** Wave 0 DR spec import (`ontology_id: "dr_spec"`), not
the placeholder.

## Overview

`input.json` pins the real content of `README.md` as it existed
in the viewer checkout at generation time. `expected.json` contains this
file's `provenance: extracted` individuals (5) and the
`extracted`-provenance relationships whose endpoints are both individuals
from this same file (0). `inferred`-provenance elements,
and any relationship touching one, are excluded entirely -- they were not
literally stated in the text, so crediting or penalizing extraction against
them would measure DR's inference step, not this pipeline's extraction.

## Distractors

`distractors.json` is intentionally empty. Wave 1's source is a real,
already-curated architecture model, not authored fixture prose -- there is
no near-miss / plausible-but-wrong data in the viewer model to derive
distractors from (design doc §5, Must-Fix 3). A future wave that authors
prose directly (Wave 2+) can add distractors deliberately; fabricating them
here would not reflect anything actually present in the source data.

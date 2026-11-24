---
date: 2026-11-21
kind: experiment
implementations: [single_call]
models: [claude-opus-5-5]
takes: 1
cost_usd: null
verdict: n/a
reproducible: partly
---

# Gate D: the default pipeline on two real documents, reviewed by a person (2026-11-21)

## Question

How does the default pipeline (`single_call` on Opus 5.5) do on real material outside the benchmark, judged by the person who has to review it? This is the Workbench's Gate D ([#1453](https://github.com/tinkermonkey/context-studio/issues/1453)): a DR platform and a House manual, each extracted into its own dataset, reviewed and applied.

## Decision rule (set in advance)

None. This is a gate measurement, not a comparison: nothing is adopted or rejected by it. The measures are the [value log's](../../../rearchitecture/ontology_workbench_proposal.md#value-log): hand edits, decisions captured, time to decision and quality held. Spend was capped at $20 for both runs, re-runs included.

## Method

- **Implementation, configuration, model:** `single_call`, `extraction-single-call`, Claude Opus 5.5. The defaults on main at 25484715, run from the Extract API on the live workspace.
- **Documents:**
  - **DR:** the documentation_robotics_viewer `README.md` (16,662 characters), into the new dataset `dr-viewer`. Source 18abd5c5, run f21bec8d, proposal 499330c5.
  - **House:** the Café refrigerator CXE22DP2PJS1 owner's manual (a 133-page PDF, the URL in House's library), into the new dataset `home`. Source 7453199f, run c8e21441, proposal 6590a1cf. Only pages 7-40, the English owner's content, were extracted. The PDF came in with no headings, so the boilerplate skip could not find the French and Spanish copies (pages 46-133) or the warranty. It skipped 3 safety sections.
- **Takes:** one each.
- **Review:** by the user, on the Review page. The 128 House relationships were accepted in bulk.
- **Budget and cost:** a $20 cap. The estimate before the runs was $3-5. The runs record only a total token count (99,360 and 129,262), with no split into input, cache and output, so actual spend is bounded: at most $4.57, pricing every token at Opus's output rate.

## Results

One take each.

| | DR viewer README | House refrigerator manual |
|---|---|---|
| Run time | 1m51s | 5m46s (4 sections, 12 relate chunks) |
| Individuals proposed | 79 | 167 |
| accepted as proposed | 69 | 153 |
| accepted with a class change | 5 | 6 |
| rejected | 5 | 7 |
| left undecided | 0 | 1 |
| Relationships proposed | 24 | 134 |
| applied | 18 | 128 |
| rejected | 6 | 0 |
| failed at apply | 0 | 5 |
| left undecided | 0 | 1 |
| Review time measured | 26.8 min over 103 decisions | 11.5 min over 121 timed decisions |
| Candidates refused before proposal (domain or range) | 1 | 4 |

What the person changed:

- **Several items in one (House, 4 rejections):** "Torx T20, T25", "Copper water supply kits WX8X2, WX8X3, WX8X4", "Straight and Phillips blade screwdriver" and "Compression nut and ferrule". Each is two or three things. The review can only reject such a node, not split it.
- **Not an element (DR, 5 rejections):** dependencies or facts stated as elements, such as "E2E tests require DR CLI server", "DR CLI v1.0.0 or higher installed globally" and "1197 tests across unit, integration, E2E".
- **A better class (11 retypes):**
  - DR: 2 Feature → TechnologyProcess (isolated and accessibility testing), 2 ApplicationFunction → SoftwareCapability (model loading, file watching), and a Node.js version requirement from Constraint → SecurityConstraints.
  - House: 2 Person → Business (plumbers), Resource → Appliance (the water and ice dispenser), Resource → Tool (SmartHQ), Supply → Tool (microfiber cloth), and Tag → Property (factory preset temperatures).
- **Relationships (DR, 6 rejections):** 1 with its direction swapped ("an update triggers the notification"), 5 with the wrong predicate ("the CLI server implements model loading", not serves). The review could not reverse them or change their ends (#1673), so they were rejected rather than corrected.
- **Other House rejections:** a duplicate ("Café" of "Cafe Appliances"), one not in the text (a wooden spoon), and one too generic.
- **House apply failures:** 4 relationships whose end the person rejected were accepted and failed at apply, instead of being rejected with it. 1 failed because its end's class changed in review (Tag → Property) and no longer fit the predicate's range. The review didn't flag either case.

## Limits

- One take per document, so no number here is comparable with the benchmark's or within its noise threshold.
- One person's review, of two documents: a README of 17K characters and 34 pages of a manual.
- The House half measures the extraction system, not a House need. House will never use its ontology to hold individuals from manuals.
- Spend is a bound, not a measurement.
- The page range for the manual was chosen by hand.

## Verdict

n/a: a gate measurement. It feeds the [Gate D reading](../../../rearchitecture/ontology_workbench_proposal.md#value-log), and adds one recommended next step to [the current state](../README.md#recommended-next-steps). Half of what the person changed (15 of 29 rejections and retypes) came down to two questions an LLM could reason about before the person sees the proposal:

- Is this extraction one item or several?
- Is this class the best fit for this node, compared with the others?

So an optional stage that reviews the extraction before a person should be designed and assessed.

## Reproduce

Partly. Both documents are public at the versions used: the viewer README at tinkermonkey/documentation_robotics_viewer 02ab31d, and the manual at its URL in the source record. To rerun, add each source, then:

```bash
curl -X POST localhost:8000/api/sources/{source_id}/extract -H 'content-type: application/json' -d '{"dataset": "dr-viewer"}'
```

For the manual, the body is `{"dataset": "home", "pages": "7-40"}`. The runs were not recorded as cassettes, and the review lives in the workspace database. Scratch; not reproducible from the repository.

## Links

- Gate D: [#1453](https://github.com/tinkermonkey/context-studio/issues/1453), roadmap lane H in [#1322](https://github.com/tinkermonkey/context-studio/issues/1322)
- Review friction found: [#1672](https://github.com/tinkermonkey/context-studio/issues/1672), [#1673](https://github.com/tinkermonkey/context-studio/issues/1673), [#1674](https://github.com/tinkermonkey/context-studio/issues/1674)
- Per-run cost: [#1573](https://github.com/tinkermonkey/context-studio/issues/1573)

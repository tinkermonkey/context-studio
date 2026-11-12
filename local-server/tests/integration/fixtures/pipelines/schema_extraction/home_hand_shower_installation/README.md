# Hand Shower Installation Schema Fixture

**Source:** Original text written for this corpus (#1570), in the style of a three-page hand shower installation sheet. Not copied or paraphrased from any manufacturer's sheet.
**Curator:** Claude (for #1570)

## Overview
A PDF-like source: `page_starts` marks three pages, which makes the run a source run, so the default boilerplate skipping applies (domain/extraction/section_filter.py). Page 1 has the parts list and tools, page 2 the steps and specifications, page 3 care and cleaning followed by a LIMITED LIFETIME WARRANTY block and a WARNING block (magnets, pacemakers, choking hazard). The section filter skips the warranty and warning blocks today. Step 9 ("Peel the clear film and the tab off the spray face") stays in the read text: it reproduces the #1570 "Tab" / "Clear Film" junk classes.

## Existing classes
`input.json` `existing_classes` (Appliance, Fixture, Part, Supply, Task, Tool) are seeded into the run's taxonomy (`ontology_id`), so new classes can be placed under them. Candidates that echo an existing class are left out of the class scores.

## Gold
- **Classes:** the fixtures, parts, tools, supplies and tasks the sheet names, each once.
- **Parents:** Hand Shower and Shower Head under Fixture; hardware under Part; tools under Tool; Plumber's Tape and White Vinegar under Supply; Installation and Cleaning under Task.
- **Attributes:** Flow Rate and Maximum Water Pressure (Hand Shower), Hose Length (Shower Hose).
- **Forbidden classes:** the specifications (measurements and units), every warranty and safety term from page 3, and Tab / Clear Film.
- Soft Cloth, Pencil, Sliding Holder, Spray Face and Magnet are neither expected nor forbidden.

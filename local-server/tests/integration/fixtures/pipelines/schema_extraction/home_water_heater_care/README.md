# Water Heater Care Schema Fixture

**Source:** Original text written for this corpus (#1570), in the style of a home water heater care web page. Not copied or paraphrased from any published page.
**Curator:** Claude (for #1570)

## Overview
A plain web page (no source keys, so no boilerplate skipping) with a yearly care routine: tank flush, relief valve test, anode rod inspection, thermostat setting. It ends with an inline scald caution, which the section filter does not see, so it measures whether the pipeline itself avoids safety junk. It is the one scenario with a hierarchy among new classes: Gas Water Heater and Electric Water Heater belong under Water Heater, itself under the existing Appliance.

## Existing classes
`input.json` `existing_classes` (Appliance, Part, Supply, Task, Tool) are seeded into the run's taxonomy (`ontology_id`), so new classes can be placed under them. Candidates that echo an existing class are left out of the class scores.

## Gold
- **Classes:** the water heater, its kinds and parts, the tools and supply used, and the three named tasks, each once.
- **Parents:** Water Heater under Appliance; Gas Water Heater and Electric Water Heater under Water Heater; components under Part; tools under Tool; Plumber's Tape under Supply; the three tasks under Task.
- **Attributes:** Tank Capacity, Temperature Setting, Recovery Rate and Energy Factor (Water Heater).
- **Forbidden classes:** those measurements, Temperature, Standby Heat Loss, Gallon, and the scald caution's terms.
- Sediment, Hard Water, Rating Plate and Faucet are neither expected nor forbidden.

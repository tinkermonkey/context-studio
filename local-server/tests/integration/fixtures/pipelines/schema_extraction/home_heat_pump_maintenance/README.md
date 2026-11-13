# Heat Pump Maintenance Schema Fixture

**Source:** Original text written for this corpus (#1570), in the style of a home-energy maintenance web page. Not copied or paraphrased from any published page.
**Curator:** Claude (for #1570)

## Overview
A plain web page (no source keys, so no boilerplate skipping) about caring for a heat pump, furnace and central air conditioner. Reproduces the #1570 ENERGY STAR run's failures: the text says "heating and cooling system", "cooling system" and "heating system" (sense-variant bait), and it names measurements (voltage, current, refrigerant charge, indoor humidity, MERV rating, setpoint, starting cycle).

## Existing classes
`input.json` `existing_classes` (Appliance, Part, Supply, Task, Tool) are seeded into the run's taxonomy (`ontology_id`), so new classes can be placed under them. Candidates that echo an existing class are left out of the class scores.

## Gold
- **Classes:** the equipment, parts, supplies and tasks the text names, each once.
- **Parents:** each class's `parent` is the class (or list of classes) it belongs under. Air Handler and Thermostat accept Appliance or Part. HVAC Contractor has no parent (nothing in the seeded taxonomy fits), so it is not scored for placement.
- **Attributes:** measurements are attributes of the class they describe (Compressor: Voltage, Current; Heat Pump: Refrigerant Charge, Indoor Humidity; Air Filter: MERV Rating; Thermostat: Setpoint). Attribute recall is scored by label, whatever class the pipeline attaches them to.
- **Forbidden classes:** the measurements, plus Starting Cycle. Any class with one of these labels (sense qualifier ignored) is a violation.
- Generic "Heating System" / "Cooling System" classes are neither expected nor forbidden; any sense variant of a term counts in `sense_duplicate_count`.

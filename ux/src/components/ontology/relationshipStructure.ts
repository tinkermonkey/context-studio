import type { components } from "@/api/types";

type PropertyDefinition = components["schemas"]["PropertyDefinitionResponse"];
type AttributeDefinition = components["schemas"]["AttributeDefinitionResponse"];

/** "0..1", "1..∞": how many relationships of a type one end may have. */
function range(min: number, max: number | null | undefined): string {
  return `${min}..${max ?? "∞"}`;
}

/**
 * A relationship type's cardinality as read in the drawer: per source (its
 * minimum and maximum) and per target (at most).
 */
export function cardinalityLabel(
  property: Pick<PropertyDefinition, "min_per_source" | "max_per_source" | "max_per_target">,
): string {
  const source = range(property.min_per_source ?? 0, property.max_per_source);
  const target = range(0, property.max_per_target);
  return `per source ${source} · per target ${target}`;
}

/** "number", "string (each, kg) required default each": an edge attribute in brief. */
export function edgeAttributeLabel(attribute: AttributeDefinition): string {
  const parts = [`${attribute.datatype}`];
  if (attribute.allowed_values?.length) parts.push(`(${attribute.allowed_values.join(", ")})`);
  if (attribute.is_required) parts.push("required");
  if (attribute.default_value) parts.push(`default ${attribute.default_value}`);
  return parts.join(" ");
}

import { Chip } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";

type RelationshipAttributeMap = components["schemas"]["RelationshipResponse"]["attributes"];

/** One attribute value as text: booleans read as yes/no, null as an em dash. */
export function formatAttributeValue(value: string | number | boolean | null): string {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

/** Attribute names in display order (alphabetical, so rows read the same everywhere). */
export function attributeEntries(attributes: RelationshipAttributeMap | undefined) {
  return Object.entries(attributes ?? {}).sort(([a], [b]) => a.localeCompare(b));
}

interface RelationshipAttributesProps {
  attributes: RelationshipAttributeMap | undefined;
  "data-testid"?: string;
}

/**
 * The values a relationship carries on its edge (a kit's quantity, unit,
 * optional), read-only, as neutral chips. Renders nothing when there are none.
 */
export function RelationshipAttributes({
  attributes,
  "data-testid": testId = "relationship-attributes",
}: RelationshipAttributesProps) {
  const entries = attributeEntries(attributes);
  if (entries.length === 0) return null;
  return (
    <span className="relationship-attributes" role="list" data-testid={testId}>
      {entries.map(([name, value]) => (
        <span key={name} role="listitem" aria-label={`${name}: ${formatAttributeValue(value)}`}>
          <Chip form="id-tag">
            {name}{" "}
            <span className="relationship-attributes__value">{formatAttributeValue(value)}</span>
          </Chip>
        </span>
      ))}
    </span>
  );
}

/**
 * Source utilities for consistent handling of reference sources across the app
 */

import { SOURCE_METADATA, SourceType } from "@/api/types/unified";

/**
 * Valid Flowbite Badge color types
 */
export type BadgeColor =
  | "info"
  | "gray"
  | "failure"
  | "success"
  | "warning"
  | "indigo"
  | "purple"
  | "pink"
  | "blue"
  | "cyan"
  | "teal"
  | "lime"
  | "green"
  | "yellow"
  | "red"
  | "orange";

/**
 * Map SOURCE_METADATA colors to Flowbite Badge colors
 * Note: Flowbite uses "warning" for orange/yellow and "failure" for red
 */
const COLOR_MAP: Record<string, BadgeColor> = {
  blue: "info", // Using "info" instead of "blue" for better visibility
  orange: "warning", // Flowbite's warning color is orange/yellow
  purple: "purple",
  red: "failure", // Flowbite's failure color is red
  gray: "gray",
};

/**
 * Normalize source name to match SOURCE_METADATA keys
 * Handles variations like "schema.org" -> "schema_org"
 */
function normalizeSourceName(source: string): string {
  // Convert to lowercase and replace dots/spaces with underscores
  return source.toLowerCase().replace(/[.\s]/g, "_");
}

/**
 * Get the badge color for a given source
 * @param source - The source identifier (e.g., "dbpedia", "conceptnet", "schema.org")
 * @returns The Flowbite badge color
 */
export function getSourceBadgeColor(source: string): BadgeColor {
  const normalizedSource = normalizeSourceName(source);
  const metadata = SOURCE_METADATA[normalizedSource as SourceType];
  if (!metadata) {
    return "gray";
  }
  return COLOR_MAP[metadata.color] || "gray";
}

/**
 * Get the source label for a given source
 * @param source - The source identifier (e.g., "dbpedia", "conceptnet")
 * @returns The human-readable source label
 */
export function getSourceLabel(source: string): string {
  const normalizedSource = normalizeSourceName(source);
  const metadata = SOURCE_METADATA[normalizedSource as SourceType];
  return metadata?.label || source;
}

/**
 * Get the full source metadata for a given source
 * @param source - The source identifier (e.g., "dbpedia", "conceptnet")
 * @returns The source metadata or undefined
 */
export function getSourceMetadata(source: string) {
  const normalizedSource = normalizeSourceName(source);
  return SOURCE_METADATA[normalizedSource as SourceType];
}

/**
 * Generate the external URL for a resource based on its source
 * @param source - The source identifier (e.g., "dbpedia", "conceptnet", "wikidata", "schema_org")
 * @param externalId - The external ID of the resource
 * @returns The URL to view the resource in its original source, or null if not supported
 */
export function getSourceUrl(
  source: string,
  externalId: string,
): string | null {
  const normalizedSource = normalizeSourceName(source);

  switch (normalizedSource) {
    case "dbpedia":
      // DBpedia resources are at http://dbpedia.org/resource/
      return `http://dbpedia.org/resource/${encodeURIComponent(externalId)}`;

    case "conceptnet":
      // ConceptNet concepts are at http://conceptnet.io/c/
      // External IDs are typically in format "/c/en/word" so we can use them directly
      if (externalId.startsWith("/")) {
        return `http://conceptnet.io${externalId}`;
      }
      return `http://conceptnet.io/c/en/${encodeURIComponent(externalId)}`;

    case "wikidata":
      // Wikidata entities are at https://www.wikidata.org/wiki/
      return `https://www.wikidata.org/wiki/${encodeURIComponent(externalId)}`;

    case "schema_org":
      // Schema.org types/properties are at https://schema.org/
      return `https://schema.org/${encodeURIComponent(externalId)}`;

    default:
      return null;
  }
}

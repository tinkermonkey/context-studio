import { useMemo, useState } from "react";
import { EntityPicker } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";
import { classLabel, layerMatesFirst } from "./reviewModel";

type ClassResponse = components["schemas"]["ClassResponse"];

/** How many matches the picker lists. */
const MATCHES_SHOWN = 20;

interface ReviewClassPickerProps {
  /** The classes to choose from: the taxonomy's classes that are not derived. */
  classes: ClassResponse[];
  /** The element's own class: left out, and its layer's classes listed first. */
  current?: ClassResponse;
  disabled?: boolean;
  /** The classes are still loading: the search waits. */
  loading?: boolean;
  onPick: (classId: string) => void;
  /** The search input's id: unique on the page (the inspector and the add form each have one). */
  inputId?: string;
  /** The label above the search; defaults to "Search all N classes". */
  label?: string;
  "data-testid"?: string;
}

/**
 * Search the taxonomy's classes by reference, title or identifier, the
 * current class's layer-mates first, and pick one for the element.
 */
export function ReviewClassPicker({
  classes,
  current,
  disabled,
  loading = false,
  onPick,
  inputId = "review-class-search",
  label,
  "data-testid": testId = "review-class-picker",
}: ReviewClassPickerProps) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return [];
    return layerMatesFirst(classes, current?.concept_scheme_id)
      .filter(
        (c) =>
          c.id !== current?.id &&
          [classLabel(c), c.title, c.identifier].some((text) =>
            text.toLowerCase().includes(needle),
          ),
      )
      .slice(0, MATCHES_SHOWN)
      .map((c) => ({ id: c.id, label: classLabel(c) }));
  }, [classes, current, query]);

  return (
    <div className="review-section" data-testid={testId}>
      <label htmlFor={inputId} className="review-muted">
        {loading ? "Loading classes…" : (label ?? `Search all ${classes.length} classes`)}
      </label>
      <EntityPicker
        inputId={inputId}
        query={query}
        onQueryChange={setQuery}
        results={results}
        onSelect={(result) => {
          setQuery("");
          onPick(result.id);
        }}
        onClear={() => setQuery("")}
        placeholder="Search classes…"
        placement="top-start"
        disabled={disabled || loading}
      />
    </div>
  );
}

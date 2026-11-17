import { useMemo, useState } from "react";
import { EntityPicker } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

/** How many matches the picker lists. */
const MATCHES_SHOWN = 20;

interface ReviewClassPickerProps {
  /** The classes to choose from: the taxonomy's classes that are not derived. */
  classes: ClassResponse[];
  /** The element's own class, left out. */
  excludeId?: string;
  disabled?: boolean;
  onPick: (classId: string) => void;
}

/** Search the taxonomy's classes by identifier or title, and pick one for the element. */
export function ReviewClassPicker({
  classes,
  excludeId,
  disabled,
  onPick,
}: ReviewClassPickerProps) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return [];
    return classes
      .filter(
        (c) =>
          c.id !== excludeId &&
          (c.identifier.toLowerCase().includes(needle) || c.title.toLowerCase().includes(needle)),
      )
      .slice(0, MATCHES_SHOWN)
      .map((c) => ({ id: c.id, label: c.identifier || c.title }));
  }, [classes, excludeId, query]);

  return (
    <div className="review-section" data-testid="review-class-picker">
      <label htmlFor="review-class-search" className="review-muted">
        Search all {classes.length} classes
      </label>
      <EntityPicker
        inputId="review-class-search"
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
        disabled={disabled}
      />
    </div>
  );
}

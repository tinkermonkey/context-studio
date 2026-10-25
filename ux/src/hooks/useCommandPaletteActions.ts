import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useCommandPaletteStore, type PaletteAction } from "@/stores/commandPalette";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClassSearch, useIndividualSearch } from "@/api/hooks/ontology/useEntitySearch";
import { useDebounce } from "@/hooks/useDebounce";
import { entityPath } from "@/lib/entityPaths";

/** Entity "Go to" actions offered per entity type. */
const ACTIONS_PER_TYPE = 5;
const SEARCH_DEBOUNCE_MS = 250;

/** Palette descriptions are matched by the palette's own filter, so include the identifier. */
function describe(identifier: string | null | undefined, text: string): string {
  return identifier ? `${identifier} · ${text}` : text;
}

/**
 * Register "Go to …" palette actions for taxonomies, schemes, classes and
 * individuals that match what the user has typed. Matching runs server-side
 * (debounced `q`, title or identifier) only while the palette is open.
 */
export function useCommandPaletteActions() {
  const navigate = useNavigate();
  const { open, query, registerActions, unregisterActions } = useCommandPaletteStore();

  const q = useDebounce(query.trim(), SEARCH_DEBOUNCE_MS) || undefined;
  const page = { q, limit: ACTIONS_PER_TYPE, sort_by: "title" as const };
  const enabled = { enabled: open, keepPrevious: true };

  const { data: taxonomies } = useTaxonomies(page, enabled);
  const { data: schemes } = useSchemes(undefined, page, enabled);
  const { data: classes } = useClassSearch(query, undefined, { enabled: open });
  const { data: individuals } = useIndividualSearch(query, undefined, { enabled: open });

  useEffect(() => {
    const dynamicActions: PaletteAction[] = [];

    (taxonomies?.items ?? []).slice(0, ACTIONS_PER_TYPE).forEach((taxonomy) => {
      dynamicActions.push({
        id: `taxonomy-${taxonomy.id}`,
        label: `Go to taxonomy · ${taxonomy.title}`,
        description: describe(taxonomy.identifier, "Taxonomy"),
        onSelect: () => {
          navigate({ to: entityPath("taxonomy", taxonomy.id) });
        },
      });
    });

    (classes?.items ?? []).slice(0, ACTIONS_PER_TYPE).forEach((classItem) => {
      dynamicActions.push({
        id: `class-${classItem.id}`,
        label: `Go to class · ${classItem.title}`,
        description: describe(classItem.identifier, classItem.description || "Class"),
        onSelect: () => {
          navigate({ to: entityPath("class", classItem.id) });
        },
      });
    });

    (individuals?.items ?? []).slice(0, ACTIONS_PER_TYPE).forEach((individual) => {
      dynamicActions.push({
        id: `individual-${individual.id}`,
        label: `Go to individual · ${individual.title}`,
        description: individual.description || "Individual",
        onSelect: () => {
          navigate({ to: entityPath("individual", individual.id) });
        },
      });
    });

    (schemes?.items ?? []).slice(0, ACTIONS_PER_TYPE).forEach((scheme) => {
      dynamicActions.push({
        id: `scheme-${scheme.id}`,
        label: `Go to scheme · ${scheme.title}`,
        description: describe(scheme.identifier, scheme.description || "Scheme"),
        onSelect: () => {
          navigate({ to: entityPath("scheme", scheme.id) });
        },
      });
    });

    if (dynamicActions.length > 0) {
      registerActions(dynamicActions);
    }

    return () => {
      if (dynamicActions.length > 0) {
        unregisterActions(dynamicActions.map((a) => a.id));
      }
    };
  }, [taxonomies, classes, individuals, schemes, registerActions, unregisterActions, navigate]);
}

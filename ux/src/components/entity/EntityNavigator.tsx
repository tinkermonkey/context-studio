import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Panel, SegmentedControl, TextInput } from "@tinkermonkey/heimdall-ui";
import {
  HierarchyTree,
  type HierarchyMode,
  type HierarchyNodeKind,
} from "@/components/ontology/HierarchyTree";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses, useClassesByIds } from "@/api/hooks/ontology/useClasses";
import { useIndividuals } from "@/api/hooks/ontology/useIndividuals";
import { SMALL_SET_LIMIT } from "@/api/config";
import { useDebounce } from "@/hooks/useDebounce";
import { entityPath } from "@/lib/entityPaths";
import { useNavigatorStore } from "@/stores/navigator";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];
type IndividualResponse = components["schemas"]["IndividualResponse"];

/** Classes / individuals matched server-side while filtering (title or identifier contains the text). */
export const NAVIGATOR_MATCH_LIMIT = 100;
const FILTER_DEBOUNCE_MS = 250;
const NO_EXPANSION: string[] = [];

/** Schema list pages: switching to Data opens the individuals list. */
export const SCHEMA_LIST_MODE_LINKS = { data: "/app/data/individuals" } as const;
/** Data list pages: switching to Schema opens the taxonomies list. */
export const DATA_LIST_MODE_LINKS = { schema: "/app/schema/taxonomies" } as const;

const MODE_OPTIONS = [
  { value: "schema", label: "Schema" },
  { value: "data", label: "Data" },
];

interface EntityNavigatorProps {
  /**
   * Mode to switch to when the page opens (schema list pages: Schema; data
   * pages: Data). Omit it to keep the current mode, so drilling down through
   * taxonomy, scheme and class pages in Data mode stays in Data mode.
   */
  defaultMode?: HierarchyMode;
  /** The node to highlight (the open page's entity). */
  selectedId?: string;
  /**
   * The node to highlight in Schema mode when `selectedId` isn't in that tree
   * (an individual page highlights the individual's class).
   */
  schemaSelectedId?: string;
  /** Ancestors of the selected node, opened so it is visible. */
  expandIds?: string[];
  /**
   * Where switching to a mode takes the user, for pages that belong to one area
   * (list pages, the individual page), so the page and the sidebar match the
   * mode. Taxonomy, scheme and class pages omit it: they work in both modes.
   */
  modeLinks?: Partial<Record<HierarchyMode, string>>;
}

interface FilteredTree {
  taxonomies: TaxonomyResponse[];
  schemes: ConceptSchemeResponse[];
  classes: ClassResponse[];
  individuals?: IndividualResponse[];
  /** Every container row in the filtered tree, all shown open. */
  openIds: Set<string>;
}

function matches(entity: { title: string; identifier?: string | null }, q: string): boolean {
  return (
    entity.title.toLowerCase().includes(q) || (entity.identifier ?? "").toLowerCase().includes(q)
  );
}

/**
 * The branches of the tree that lead to a match: matching classes (and in
 * Data mode matching individuals, both searched on the server so unloaded
 * branches are covered) under their scheme and taxonomy, plus taxonomies and
 * schemes whose own title matches.
 */
function filterTree(
  q: string,
  taxonomies: TaxonomyResponse[],
  schemes: ConceptSchemeResponse[],
  classes: ClassResponse[],
  individuals?: IndividualResponse[],
): FilteredTree {
  const matchedTaxonomyIds = new Set(taxonomies.filter((t) => matches(t, q)).map((t) => t.id));
  const schemeIdsWithClasses = new Set(classes.map((c) => c.concept_scheme_id));
  const keptSchemes = schemes.filter(
    (s) => matches(s, q) || schemeIdsWithClasses.has(s.id) || matchedTaxonomyIds.has(s.taxonomy_id),
  );
  const taxonomyIdsWithSchemes = new Set(keptSchemes.map((s) => s.taxonomy_id));
  const keptTaxonomies = taxonomies.filter(
    (t) => matchedTaxonomyIds.has(t.id) || taxonomyIdsWithSchemes.has(t.id),
  );
  const classIdsWithIndividuals = new Set((individuals ?? []).flatMap((i) => i.class_ids));
  return {
    taxonomies: keptTaxonomies,
    schemes: keptSchemes,
    classes,
    individuals,
    openIds: new Set([
      ...keptTaxonomies.map((t) => t.id),
      ...schemeIdsWithClasses,
      ...classIdsWithIndividuals,
    ]),
  };
}

/**
 * The knowledge-graph tree beside schema, data and entity pages. Schema mode
 * shows taxonomy → scheme → class; Data mode adds individuals under their
 * classes (a page at a time) and counts individuals. Choosing a node opens its
 * page. The tree keeps the rows the user opened across pages, opens to and
 * highlights the current node (scrolling it into view once its row has
 * loaded), and can be filtered by title.
 */
export function EntityNavigator({
  defaultMode,
  selectedId,
  schemaSelectedId,
  expandIds = NO_EXPANSION,
  modeLinks,
}: EntityNavigatorProps) {
  const navigate = useNavigate();
  const treeRef = useRef<HTMLDivElement>(null);
  const mode = useNavigatorStore((s) => s.mode);
  const setMode = useNavigatorStore((s) => s.setMode);
  const dataMode = mode === "data";
  const [filterText, setFilterText] = useState("");
  const q = useDebounce(filterText.trim(), FILTER_DEBOUNCE_MS).toLowerCase();
  const filtering = q.length > 0;

  const expandedIds = useNavigatorStore((s) => s.expandedIds);
  const setExpanded = useNavigatorStore((s) => s.setExpanded);
  const expand = useNavigatorStore((s) => s.expand);

  const {
    data: taxonomiesResponse,
    isLoading: taxonomiesLoading,
    error,
  } = useTaxonomies({ limit: SMALL_SET_LIMIT });
  const { data: schemesResponse, isLoading: schemesLoading } = useSchemes(undefined, {
    limit: SMALL_SET_LIMIT,
  });
  const matchParams = { q, limit: NAVIGATOR_MATCH_LIMIT, sort_by: "title" as const };
  const { data: classMatches, isFetching: classesFetching } = useClasses(matchParams, {
    enabled: filtering,
    keepPrevious: true,
  });
  const { data: individualMatches, isFetching: individualsFetching } = useIndividuals(matchParams, {
    enabled: filtering && dataMode,
    keepPrevious: true,
  });
  // The classes the matching individuals belong to (they may not match themselves).
  const { data: individualClasses } = useClassesByIds(
    filtering && dataMode ? (individualMatches?.items ?? []).flatMap((i) => i.class_ids) : [],
  );

  // Apply the page's mode before paint.
  useLayoutEffect(() => {
    if (defaultMode) setMode(defaultMode);
  }, [defaultMode, setMode]);

  // Open the current node's path before paint, keeping whatever else is open.
  const expandKey = expandIds.join("|");
  useLayoutEffect(() => {
    if (expandKey) expand(expandKey.split("|"));
  }, [expandKey, expand]);

  const filtered = useMemo(() => {
    if (!filtering) return null;
    const individuals = dataMode ? (individualMatches?.items ?? []) : undefined;
    const classById = new Map<string, ClassResponse>();
    for (const cls of [
      ...(classMatches?.items ?? []),
      ...(dataMode ? (individualClasses?.items ?? []) : []),
    ]) {
      classById.set(cls.id, cls);
    }
    return filterTree(
      q,
      taxonomiesResponse?.items ?? [],
      schemesResponse?.items ?? [],
      [...classById.values()],
      individuals,
    );
  }, [
    filtering,
    dataMode,
    q,
    taxonomiesResponse,
    schemesResponse,
    classMatches,
    individualMatches,
    individualClasses,
  ]);

  const highlightedId = dataMode ? selectedId : (schemaSelectedId ?? selectedId);

  // Classes and individuals load lazily, so wait for the selected row to appear.
  useEffect(() => {
    const container = treeRef.current;
    if (!container || !highlightedId) return;
    const scrollToSelected = () => {
      const row = container.querySelector(`[data-testid="hierarchy-node-${highlightedId}"]`);
      if (!row) return false;
      row.scrollIntoView?.({ block: "nearest" });
      return true;
    };
    if (scrollToSelected()) return;
    const observer = new MutationObserver(() => {
      if (scrollToSelected()) observer.disconnect();
    });
    observer.observe(container, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [highlightedId, mode]);

  const openNode = (kind: HierarchyNodeKind, id: string) => navigate({ to: entityPath(kind, id) });
  const changeMode = (next: HierarchyMode) => {
    setMode(next);
    const to = modeLinks?.[next];
    if (to) navigate({ to });
  };
  const fetching = classesFetching || (dataMode && individualsFetching);
  const truncated: string[] = [];
  if ((classMatches?.total ?? 0) > (classMatches?.items.length ?? 0)) truncated.push("classes");
  if (dataMode && (individualMatches?.total ?? 0) > (individualMatches?.items.length ?? 0)) {
    truncated.push("individuals");
  }

  return (
    <nav aria-label="Navigator" data-testid="entity-navigator">
      <Panel
        title="Navigator"
        noPadding
        headerAction={
          <SegmentedControl
            value={mode}
            onChange={(value) => changeMode(value as HierarchyMode)}
            options={MODE_OPTIONS}
            aria-label="Tree mode"
            data-testid="navigator-mode"
          />
        }
      >
        <div className="entity-navigator__filter">
          <TextInput
            type="search"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="Filter tree…"
            aria-label="Filter the tree"
            data-testid="navigator-filter"
          />
        </div>
        {dataMode && !filtering && (
          <p className="entity-note entity-navigator__note">Counts show individuals.</p>
        )}
        <div ref={treeRef} className="entity-navigator__tree">
          {filtered ? (
            filtered.taxonomies.length === 0 ? (
              <p className="entity-note entity-navigator__note" data-testid="navigator-no-matches">
                {fetching ? "Searching…" : `Nothing matches “${filterText.trim()}”.`}
              </p>
            ) : (
              <>
                <HierarchyTree
                  mode={mode}
                  taxonomies={filtered.taxonomies}
                  schemes={filtered.schemes}
                  classes={filtered.classes}
                  individuals={filtered.individuals}
                  selectedId={highlightedId}
                  expandedIds={filtered.openIds}
                  onSelectNode={openNode}
                  hideCounts
                  compact
                />
                {truncated.length > 0 && (
                  <p className="entity-note entity-navigator__note">
                    Showing the first {NAVIGATOR_MATCH_LIMIT} matching {truncated.join(" and ")}.
                  </p>
                )}
              </>
            )
          ) : (
            <HierarchyTree
              mode={mode}
              taxonomies={taxonomiesResponse?.items}
              schemes={schemesResponse?.items}
              loading={taxonomiesLoading || schemesLoading}
              error={error}
              selectedId={highlightedId}
              expandedIds={expandedIds}
              onExpandedChange={setExpanded}
              onSelectNode={openNode}
              compact
            />
          )}
        </div>
      </Panel>
    </nav>
  );
}

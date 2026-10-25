import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Panel, TextInput } from "@tinkermonkey/heimdall-ui";
import { HierarchyTree } from "@/components/ontology/HierarchyTree";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { SMALL_SET_LIMIT } from "@/api/config";
import { useDebounce } from "@/hooks/useDebounce";
import { entityPath } from "@/lib/entityPaths";
import { useNavigatorStore } from "@/stores/navigator";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];

/** Classes matched server-side while filtering (title or identifier contains the text). */
export const NAVIGATOR_CLASS_MATCH_LIMIT = 100;
const FILTER_DEBOUNCE_MS = 250;
const NO_EXPANSION: string[] = [];

interface EntityNavigatorProps {
  /** The node to highlight (the open page's entity, or its nearest node in the tree). */
  selectedId?: string;
  /** Ancestors of the selected node, opened so it is visible. */
  expandIds?: string[];
}

interface FilteredTree {
  taxonomies: TaxonomyResponse[];
  schemes: ConceptSchemeResponse[];
  classes: ClassResponse[];
  /** Every row in the filtered tree, all shown open. */
  openIds: Set<string>;
}

function matches(entity: { title: string; identifier?: string | null }, q: string): boolean {
  return (
    entity.title.toLowerCase().includes(q) || (entity.identifier ?? "").toLowerCase().includes(q)
  );
}

/**
 * The branches of the tree that lead to a match: matching classes (searched on
 * the server, so unloaded schemes are covered) under their scheme and
 * taxonomy, plus taxonomies and schemes whose own title matches.
 */
function filterTree(
  q: string,
  taxonomies: TaxonomyResponse[],
  schemes: ConceptSchemeResponse[],
  classes: ClassResponse[],
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
  return {
    taxonomies: keptTaxonomies,
    schemes: keptSchemes,
    classes,
    openIds: new Set([...keptTaxonomies.map((t) => t.id), ...schemeIdsWithClasses]),
  };
}

/**
 * The knowledge-graph tree beside schema and entity pages (taxonomy → scheme
 * → class). Choosing a node opens its page. The tree keeps the rows the user
 * opened across pages, opens to and highlights the current node (scrolling it
 * into view once its row has loaded), and can be filtered by title.
 */
export function EntityNavigator({ selectedId, expandIds = NO_EXPANSION }: EntityNavigatorProps) {
  const navigate = useNavigate();
  const treeRef = useRef<HTMLDivElement>(null);
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
  const { data: classMatches, isFetching: classesFetching } = useClasses(
    { q, limit: NAVIGATOR_CLASS_MATCH_LIMIT, sort_by: "title" },
    { enabled: filtering, keepPrevious: true },
  );

  // Open the current node's path before paint, keeping whatever else is open.
  const expandKey = expandIds.join("|");
  useLayoutEffect(() => {
    if (expandKey) expand(expandKey.split("|"));
  }, [expandKey, expand]);

  const filtered = useMemo(
    () =>
      filtering
        ? filterTree(
            q,
            taxonomiesResponse?.items ?? [],
            schemesResponse?.items ?? [],
            classMatches?.items ?? [],
          )
        : null,
    [filtering, q, taxonomiesResponse, schemesResponse, classMatches],
  );

  // Classes load lazily per scheme, so wait for the selected row to appear.
  useEffect(() => {
    const container = treeRef.current;
    if (!container || !selectedId) return;
    const scrollToSelected = () => {
      const row = container.querySelector(`[data-testid="hierarchy-node-${selectedId}"]`);
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
  }, [selectedId]);

  const openNode = (kind: "taxonomy" | "scheme" | "class", id: string) =>
    navigate({ to: entityPath(kind, id) });
  const classTotal = classMatches?.total ?? 0;

  return (
    <nav aria-label="Navigator" data-testid="entity-navigator">
      <Panel title="Navigator" noPadding>
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
        <div ref={treeRef} className="entity-navigator__tree">
          {filtered ? (
            filtered.taxonomies.length === 0 ? (
              <p className="entity-note entity-navigator__note" data-testid="navigator-no-matches">
                {classesFetching ? "Searching…" : `Nothing matches “${filterText.trim()}”.`}
              </p>
            ) : (
              <>
                <HierarchyTree
                  taxonomies={filtered.taxonomies}
                  schemes={filtered.schemes}
                  classes={filtered.classes}
                  selectedId={selectedId}
                  expandedIds={filtered.openIds}
                  onSelectNode={openNode}
                  compact
                />
                {classTotal > filtered.classes.length && (
                  <p className="entity-note entity-navigator__note">
                    Showing the first {filtered.classes.length} of {classTotal} matching classes.
                  </p>
                )}
              </>
            )
          ) : (
            <HierarchyTree
              taxonomies={taxonomiesResponse?.items}
              schemes={schemesResponse?.items}
              loading={taxonomiesLoading || schemesLoading}
              error={error}
              selectedId={selectedId}
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

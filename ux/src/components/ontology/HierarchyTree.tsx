import { Fragment, useMemo, useState } from "react";
import { HierarchyTree as HeimdallHierarchyTree, HierarchyRow } from "@tinkermonkey/heimdall-ui";
import { EmptyState } from "@/components/ui/EmptyState";
import { DemoDatasetPicker } from "@/components/demo/DemoDatasetPicker";
import { useClasses, useClassCountsByScheme } from "@/api/hooks/ontology/useClasses";
import { useIndividuals } from "@/api/hooks/ontology/useIndividuals";
import {
  useClassCounts,
  useSchemeCountsForTaxonomies,
} from "@/api/hooks/ontology/useContentCounts";
import { SMALL_SET_LIMIT } from "@/api/config";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];
type IndividualResponse = components["schemas"]["IndividualResponse"];

/** Individuals shown when a class first opens in Data mode, and added per "+ N more". */
export const INDIVIDUALS_FIRST_PAGE = 10;
export const INDIVIDUALS_MORE_PAGE = 25;

export type HierarchyNodeKind = "taxonomy" | "scheme" | "class" | "individual";
export type HierarchyMode = "schema" | "data";

export interface HierarchyTreeProps {
  taxonomies?: TaxonomyResponse[];
  schemes?: ConceptSchemeResponse[];
  /**
   * Classes to place under their schemes. Omit it to load lazily instead: each
   * scheme shows a server count and fetches its own classes when expanded.
   */
  classes?: ClassResponse[];
  /**
   * Data mode: individuals to place under their classes. Omit it to load
   * lazily instead, a page at a time per opened class.
   */
  individuals?: IndividualResponse[];
  /** Schema mode stops at classes; Data mode adds individuals and counts individuals. */
  mode?: HierarchyMode;
  loading?: boolean;
  error?: Error | null;
  onSelectClass?: (classId: string) => void;
  /**
   * Navigator mode: called when any row is chosen. A container row then opens
   * (and toggles when it is already the selected node) instead of only toggling.
   */
  onSelectNode?: (kind: HierarchyNodeKind, id: string) => void;
  /** Highlight this node (any kind), e.g. the open entity page. */
  selectedId?: string;
  /**
   * Controlled expansion (the Navigator keeps it in a store so it survives
   * page changes). Omit it and the tree manages its own, seeding the first
   * taxonomy and scheme open.
   */
  expandedIds?: ReadonlySet<string>;
  /** Called when a row opens or closes under controlled expansion. */
  onExpandedChange?: (id: string, open: boolean) => void;
  /** Narrow column (the Navigator): rows show no description. */
  compact?: boolean;
  /** Hide the count on every row (e.g. while the tree shows filter matches). */
  hideCounts?: boolean;
}

function countLabel(n: number, singular: string, plural: string): string {
  return `${n} ${n === 1 ? singular : plural}`;
}

function individualsLabel(n: number | undefined): string | undefined {
  return n === undefined ? undefined : countLabel(n, "individual", "individuals");
}

/** What class rows need from the tree, shared by the lazy and eager variants. */
interface ClassRowContext {
  mode: HierarchyMode;
  compact: boolean;
  hideCounts: boolean;
  selectedId?: string;
  expandedIds: ReadonlySet<string>;
  onSelectClass: (classId: string) => void;
  onSelectIndividual: (individualId: string) => void;
}

function IndividualRow({
  individual,
  ctx,
}: {
  individual: IndividualResponse;
  ctx: ClassRowContext;
}) {
  // Heimdall's HierarchyRow has no 'individual' kind: a class row without its
  // badge, tagged by a class the Navigator styles as an individual.
  return (
    <HierarchyRow
      depth={3}
      domain="default"
      kind="class"
      showKind={false}
      className="hierarchy-row--individual"
      label={individual.title}
      selected={ctx.selectedId === individual.id}
      onSelect={() => ctx.onSelectIndividual(individual.id)}
      data-testid={`hierarchy-node-${individual.id}`}
    />
  );
}

/** An opened class's individuals, a page at a time, keeping the selected one visible. */
function LazyClassIndividuals({ cls, ctx }: { cls: ClassResponse; ctx: ClassRowContext }) {
  const [limit, setLimit] = useState(INDIVIDUALS_FIRST_PAGE);
  const { data } = useIndividuals(
    { class_id: cls.id, limit, sort_by: "title" },
    { keepPrevious: true },
  );
  const items = data?.items ?? [];
  const selectedInPage = items.some((i) => i.id === ctx.selectedId);
  // The selected individual may sit past the loaded page: fetch just it (the
  // class filter returns nothing when it belongs to another class).
  const { data: pinned } = useIndividuals(
    { class_id: cls.id, ids: ctx.selectedId ? [ctx.selectedId] : [], limit: 1 },
    { enabled: !!ctx.selectedId && !!data && !selectedInPage },
  );
  const pinnedItem = selectedInPage ? undefined : pinned?.items[0];
  const remaining = (data?.total ?? 0) - items.length;

  return (
    <>
      {items.map((ind) => (
        <IndividualRow key={ind.id} individual={ind} ctx={ctx} />
      ))}
      {pinnedItem && <IndividualRow individual={pinnedItem} ctx={ctx} />}
      {remaining > 0 && (
        <HierarchyRow
          depth={3}
          domain="default"
          kind="class"
          showKind={false}
          className="hierarchy-row--more"
          label={`+ ${remaining} more in ${cls.title}`}
          onSelect={() => setLimit((n) => n + INDIVIDUALS_MORE_PAGE)}
          data-testid={`hierarchy-more-${cls.id}`}
        />
      )}
    </>
  );
}

interface ClassRowsProps {
  classes: ClassResponse[];
  ctx: ClassRowContext;
  /** Data mode: individual count per class id (missing while loading). */
  individualCounts?: Map<string, number>;
  /** Eager individuals per class id (filter results); omit to load lazily. */
  individualsByClass?: Map<string, IndividualResponse[]>;
}

function ClassRows({ classes, ctx, individualCounts, individualsByClass }: ClassRowsProps) {
  const dataMode = ctx.mode === "data";
  return (
    <>
      {classes.map((cls) => {
        const open = dataMode && ctx.expandedIds.has(cls.id);
        return (
          <Fragment key={cls.id}>
            <HierarchyRow
              depth={2}
              domain="default"
              kind="class"
              label={cls.title}
              meta={
                dataMode && !ctx.hideCounts
                  ? individualsLabel(individualCounts?.get(cls.id))
                  : undefined
              }
              description={ctx.compact ? undefined : (cls.description ?? "")}
              selected={ctx.selectedId === cls.id}
              aria-expanded={dataMode ? open : undefined}
              onSelect={() => ctx.onSelectClass(cls.id)}
              data-testid={`hierarchy-node-${cls.id}`}
            />
            {open &&
              (individualsByClass ? (
                (individualsByClass.get(cls.id) ?? []).map((ind) => (
                  <IndividualRow key={ind.id} individual={ind} ctx={ctx} />
                ))
              ) : (
                <LazyClassIndividuals cls={cls} ctx={ctx} />
              ))}
          </Fragment>
        );
      })}
    </>
  );
}

/** An expanded scheme's classes, fetched for that scheme only (bounded, by title). */
function LazySchemeClasses({ schemeId, ctx }: { schemeId: string; ctx: ClassRowContext }) {
  const { data } = useClasses({
    concept_scheme_id: schemeId,
    limit: SMALL_SET_LIMIT,
    sort_by: "title",
  });
  const { data: counts } = useClassCounts(ctx.mode === "data" ? schemeId : undefined);
  const individualCounts = useMemo(
    () => new Map((counts ?? []).map((c) => [c.class_id, c.individual_count])),
    [counts],
  );
  return <ClassRows classes={data?.items ?? []} ctx={ctx} individualCounts={individualCounts} />;
}

export function HierarchyTree({
  taxonomies,
  schemes,
  classes,
  individuals,
  mode = "schema",
  loading = false,
  error = null,
  onSelectClass,
  onSelectNode,
  selectedId,
  expandedIds: controlledExpandedIds,
  onExpandedChange,
  compact = false,
  hideCounts = false,
}: HierarchyTreeProps) {
  const dataMode = mode === "data";
  const sortedTaxonomies = useMemo(
    () => [...(taxonomies ?? [])].sort((a, b) => a.title.localeCompare(b.title)),
    [taxonomies],
  );
  const schemesByTaxonomy = useMemo(() => {
    const map = new Map<string, ConceptSchemeResponse[]>();
    (schemes ?? []).forEach((scheme) => {
      const list = map.get(scheme.taxonomy_id) ?? [];
      list.push(scheme);
      map.set(scheme.taxonomy_id, list);
    });
    map.forEach((list) => list.sort((a, b) => a.title.localeCompare(b.title)));
    return map;
  }, [schemes]);
  const lazy = classes === undefined;
  const schemeIds = useMemo(() => (schemes ?? []).map((s) => s.id), [schemes]);
  const lazyClassCounts = useClassCountsByScheme(lazy && !dataMode && !hideCounts ? schemeIds : []);
  const taxonomyIds = useMemo(() => sortedTaxonomies.map((t) => t.id), [sortedTaxonomies]);
  const schemeCounts = useSchemeCountsForTaxonomies(dataMode && !hideCounts ? taxonomyIds : []);
  const classesByScheme = useMemo(() => {
    const map = new Map<string, ClassResponse[]>();
    (classes ?? []).forEach((cls) => {
      const list = map.get(cls.concept_scheme_id) ?? [];
      list.push(cls);
      map.set(cls.concept_scheme_id, list);
    });
    map.forEach((list) => list.sort((a, b) => a.title.localeCompare(b.title)));
    return map;
  }, [classes]);
  const individualsByClass = useMemo(() => {
    if (individuals === undefined) return undefined;
    const map = new Map<string, IndividualResponse[]>();
    individuals.forEach((ind) =>
      ind.class_ids.forEach((classId) => {
        const list = map.get(classId) ?? [];
        list.push(ind);
        map.set(classId, list);
      }),
    );
    map.forEach((list) => list.sort((a, b) => a.title.localeCompare(b.title)));
    return map;
  }, [individuals]);

  const [localExpandedIds, setLocalExpandedIds] = useState<Set<string>>(new Set());
  const [seeded, setSeeded] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState<string | undefined>(undefined);
  const [demoPickerOpen, setDemoPickerOpen] = useState(false);
  const controlled = controlledExpandedIds !== undefined;
  const expandedIds: ReadonlySet<string> = controlledExpandedIds ?? localExpandedIds;

  // Uncontrolled: seed the first taxonomy and its first scheme open, matching the reference design.
  if (!controlled && !seeded && sortedTaxonomies.length > 0) {
    const firstTaxonomy = sortedTaxonomies[0];
    const firstScheme = schemesByTaxonomy.get(firstTaxonomy.id)?.[0];
    const initial = new Set<string>([firstTaxonomy.id]);
    if (firstScheme) initial.add(firstScheme.id);
    setLocalExpandedIds(initial);
    setSeeded(true);
  }

  const setOpen = (id: string, open: boolean) => {
    if (controlled) {
      onExpandedChange?.(id, open);
      return;
    }
    setLocalExpandedIds((prev) => {
      const next = new Set(prev);
      if (open) next.add(id);
      else next.delete(id);
      return next;
    });
  };
  const toggle = (id: string) => setOpen(id, !expandedIds.has(id));

  // Navigator mode opens a row and reports it; a second click on the selected row toggles it.
  const handleSelectContainer = (kind: HierarchyNodeKind, id: string) => {
    if (!onSelectNode || selectedId === id) {
      toggle(id);
      return;
    }
    setOpen(id, true);
    onSelectNode(kind, id);
  };

  const ctx: ClassRowContext = {
    mode,
    compact,
    hideCounts,
    selectedId: selectedId ?? selectedClassId,
    expandedIds,
    onSelectClass: (classId) => {
      setSelectedClassId(classId);
      onSelectClass?.(classId);
      // In Data mode a class is a container of individuals.
      if (dataMode) handleSelectContainer("class", classId);
      else onSelectNode?.("class", classId);
    },
    onSelectIndividual: (individualId) => onSelectNode?.("individual", individualId),
  };

  if (error) {
    return (
      <EmptyState
        title="Error"
        description={error.message || "Failed to load class hierarchy"}
        variant="compact"
      />
    );
  }

  if (loading) {
    return (
      <div className="stack">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="skeleton"
            style={{
              height: "28px",
              borderRadius: "var(--radius-md, 6px)",
              marginLeft: `${(i % 3) * 20}px`,
            }}
          />
        ))}
      </div>
    );
  }

  if (sortedTaxonomies.length === 0) {
    return (
      <>
        <EmptyState
          title="No structure yet"
          description="Load a curated demo dataset to explore the workspace with a real ontology."
          action={{
            label: "Load Demo Dataset",
            onClick: () => setDemoPickerOpen(true),
          }}
          variant="compact"
        />
        <DemoDatasetPicker open={demoPickerOpen} onClose={() => setDemoPickerOpen(false)} />
      </>
    );
  }

  const schemeMeta = (scheme: ConceptSchemeResponse): string | undefined => {
    if (hideCounts) return undefined;
    if (dataMode) return individualsLabel(schemeCounts.get(scheme.id)?.individual_count);
    const count = lazy
      ? (lazyClassCounts[scheme.id] ?? 0)
      : (classesByScheme.get(scheme.id) ?? []).length;
    return countLabel(count, "class", "classes");
  };
  const taxonomyMeta = (taxonomySchemes: ConceptSchemeResponse[]): string | undefined => {
    if (hideCounts) return undefined;
    if (!dataMode) return countLabel(taxonomySchemes.length, "scheme", "schemes");
    const counts = taxonomySchemes.map((s) => schemeCounts.get(s.id)?.individual_count);
    if (counts.some((n) => n === undefined)) return undefined;
    return individualsLabel(counts.reduce<number>((sum, n) => sum + (n ?? 0), 0));
  };

  return (
    <HeimdallHierarchyTree>
      {sortedTaxonomies.map((taxonomy) => {
        const taxonomySchemes = schemesByTaxonomy.get(taxonomy.id) ?? [];
        const taxonomyOpen = expandedIds.has(taxonomy.id);
        return (
          <Fragment key={taxonomy.id}>
            <HierarchyRow
              depth={0}
              domain="default"
              kind="taxonomy"
              label={taxonomy.title}
              meta={taxonomyMeta(taxonomySchemes)}
              description={compact ? undefined : (taxonomy.description ?? "")}
              selected={selectedId === taxonomy.id}
              aria-expanded={taxonomyOpen}
              onSelect={() => handleSelectContainer("taxonomy", taxonomy.id)}
              data-testid={`hierarchy-node-${taxonomy.id}`}
            />
            {taxonomyOpen &&
              taxonomySchemes.map((scheme) => {
                const schemeOpen = expandedIds.has(scheme.id);
                return (
                  <Fragment key={scheme.id}>
                    <HierarchyRow
                      depth={1}
                      domain="default"
                      kind="scheme"
                      label={scheme.title}
                      meta={schemeMeta(scheme)}
                      description={compact ? undefined : (scheme.description ?? "")}
                      selected={selectedId === scheme.id}
                      aria-expanded={schemeOpen}
                      onSelect={() => handleSelectContainer("scheme", scheme.id)}
                      data-testid={`hierarchy-node-${scheme.id}`}
                    />
                    {schemeOpen &&
                      (lazy ? (
                        <LazySchemeClasses schemeId={scheme.id} ctx={ctx} />
                      ) : (
                        <ClassRows
                          classes={classesByScheme.get(scheme.id) ?? []}
                          ctx={ctx}
                          individualsByClass={individualsByClass}
                        />
                      ))}
                  </Fragment>
                );
              })}
          </Fragment>
        );
      })}
    </HeimdallHierarchyTree>
  );
}

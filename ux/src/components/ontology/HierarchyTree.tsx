import { Fragment, useMemo, useState } from "react";
import { HierarchyTree as HeimdallHierarchyTree, HierarchyRow } from "@tinkermonkey/heimdall-ui";
import { EmptyState } from "@/components/ui/EmptyState";
import { DemoDatasetPicker } from "@/components/demo/DemoDatasetPicker";
import { useClasses, useClassCountsByScheme } from "@/api/hooks/ontology/useClasses";
import { SMALL_SET_LIMIT } from "@/api/config";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];

export interface HierarchyTreeProps {
  taxonomies?: TaxonomyResponse[];
  schemes?: ConceptSchemeResponse[];
  /**
   * Classes to place under their schemes. Omit it to load lazily instead: each
   * scheme shows a server count and fetches its own classes when expanded.
   */
  classes?: ClassResponse[];
  loading?: boolean;
  error?: Error | null;
  onSelectClass?: (classId: string) => void;
  /**
   * Navigator mode: called when any row is chosen. A taxonomy or scheme row
   * then opens (and toggles when it is already the selected node) instead of
   * only toggling.
   */
  onSelectNode?: (kind: HierarchyNodeKind, id: string) => void;
  /** Highlight this node (taxonomy, scheme or class id), e.g. the open entity page. */
  selectedId?: string;
  /** Rows to open, e.g. the selected node's ancestors; replaces the default seeding. */
  expandIds?: string[];
  /** Narrow column (the Navigator): rows show no description. */
  compact?: boolean;
}

export type HierarchyNodeKind = "taxonomy" | "scheme" | "class";

function countLabel(n: number, singular: string, plural: string): string {
  return `${n} ${n === 1 ? singular : plural}`;
}

interface ClassRowsProps {
  classes: ClassResponse[];
  selectedClassId?: string;
  onSelect: (classId: string) => void;
  compact?: boolean;
}

function ClassRows({ classes, selectedClassId, onSelect, compact }: ClassRowsProps) {
  return (
    <>
      {classes.map((cls) => (
        <HierarchyRow
          key={cls.id}
          depth={2}
          domain="default"
          kind="class"
          label={cls.title}
          description={compact ? undefined : (cls.description ?? "")}
          selected={selectedClassId === cls.id}
          onSelect={() => onSelect(cls.id)}
          data-testid={`hierarchy-node-${cls.id}`}
        />
      ))}
    </>
  );
}

/** An expanded scheme's classes, fetched for that scheme only (bounded, by title). */
function LazySchemeClasses({
  schemeId,
  ...rest
}: Omit<ClassRowsProps, "classes"> & { schemeId: string }) {
  const { data } = useClasses({
    concept_scheme_id: schemeId,
    limit: SMALL_SET_LIMIT,
    sort_by: "title",
  });
  return <ClassRows classes={data?.items ?? []} {...rest} />;
}

export function HierarchyTree({
  taxonomies,
  schemes,
  classes,
  loading = false,
  error = null,
  onSelectClass,
  onSelectNode,
  selectedId,
  expandIds,
  compact = false,
}: HierarchyTreeProps) {
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
  const lazyClassCounts = useClassCountsByScheme(lazy ? schemeIds : []);
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

  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [seeded, setSeeded] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState<string | undefined>(undefined);
  const [demoPickerOpen, setDemoPickerOpen] = useState(false);
  const expandKey = expandIds?.join("|") ?? null;
  const [appliedExpandKey, setAppliedExpandKey] = useState<string | null>(null);

  // Open the requested rows whenever they change (keeping rows the user opened).
  if (expandKey !== null && expandKey !== appliedExpandKey) {
    setExpandedIds((prev) => new Set([...prev, ...(expandIds ?? [])]));
    setAppliedExpandKey(expandKey);
    setSeeded(true);
  }

  // Otherwise seed the first taxonomy and its first scheme open, matching the reference design.
  if (!seeded && expandKey === null && sortedTaxonomies.length > 0) {
    const firstTaxonomy = sortedTaxonomies[0];
    const firstScheme = schemesByTaxonomy.get(firstTaxonomy.id)?.[0];
    const initial = new Set<string>([firstTaxonomy.id]);
    if (firstScheme) initial.add(firstScheme.id);
    setExpandedIds(initial);
    setSeeded(true);
  }

  const toggle = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectClass = (classId: string) => {
    setSelectedClassId(classId);
    onSelectClass?.(classId);
    onSelectNode?.("class", classId);
  };

  // Navigator mode opens a row and reports it; a second click on the selected row toggles it.
  const handleSelectContainer = (kind: HierarchyNodeKind, id: string) => {
    if (!onSelectNode || selectedId === id) {
      toggle(id);
      return;
    }
    setExpandedIds((prev) => new Set(prev).add(id));
    onSelectNode(kind, id);
  };
  const highlightedClassId = selectedId ?? selectedClassId;

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
              meta={countLabel(taxonomySchemes.length, "scheme", "schemes")}
              description={compact ? undefined : (taxonomy.description ?? "")}
              selected={selectedId === taxonomy.id}
              aria-expanded={taxonomyOpen}
              onSelect={() => handleSelectContainer("taxonomy", taxonomy.id)}
              data-testid={`hierarchy-node-${taxonomy.id}`}
            />
            {taxonomyOpen &&
              taxonomySchemes.map((scheme) => {
                const schemeClasses = classesByScheme.get(scheme.id) ?? [];
                const classCount = lazy ? (lazyClassCounts[scheme.id] ?? 0) : schemeClasses.length;
                const schemeOpen = expandedIds.has(scheme.id);
                return (
                  <Fragment key={scheme.id}>
                    <HierarchyRow
                      depth={1}
                      domain="default"
                      kind="scheme"
                      label={scheme.title}
                      meta={countLabel(classCount, "class", "classes")}
                      description={compact ? undefined : (scheme.description ?? "")}
                      selected={selectedId === scheme.id}
                      aria-expanded={schemeOpen}
                      onSelect={() => handleSelectContainer("scheme", scheme.id)}
                      data-testid={`hierarchy-node-${scheme.id}`}
                    />
                    {schemeOpen &&
                      (lazy ? (
                        <LazySchemeClasses
                          schemeId={scheme.id}
                          selectedClassId={highlightedClassId}
                          onSelect={handleSelectClass}
                          compact={compact}
                        />
                      ) : (
                        <ClassRows
                          classes={schemeClasses}
                          selectedClassId={highlightedClassId}
                          onSelect={handleSelectClass}
                          compact={compact}
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

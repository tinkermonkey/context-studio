import { Fragment, useMemo, useState } from "react";
import { HierarchyTree as HeimdallHierarchyTree, HierarchyRow } from "@tinkermonkey/heimdall-ui";
import { EmptyState } from "@/components/ui/EmptyState";
import { DemoDatasetPicker } from "@/components/demo/DemoDatasetPicker";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];

export interface HierarchyTreeProps {
  taxonomies?: TaxonomyResponse[];
  schemes?: ConceptSchemeResponse[];
  classes?: ClassResponse[];
  loading?: boolean;
  error?: Error | null;
  onSelectClass?: (classId: string) => void;
}

function countLabel(n: number, singular: string, plural: string): string {
  return `${n} ${n === 1 ? singular : plural}`;
}

export function HierarchyTree({
  taxonomies,
  schemes,
  classes,
  loading = false,
  error = null,
  onSelectClass,
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

  // Seed the first taxonomy and its first scheme open, matching the reference design.
  if (!seeded && sortedTaxonomies.length > 0) {
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
              description={taxonomy.description ?? ""}
              onSelect={() => toggle(taxonomy.id)}
              data-testid={`hierarchy-node-${taxonomy.id}`}
            />
            {taxonomyOpen &&
              taxonomySchemes.map((scheme) => {
                const schemeClasses = classesByScheme.get(scheme.id) ?? [];
                const schemeOpen = expandedIds.has(scheme.id);
                return (
                  <Fragment key={scheme.id}>
                    <HierarchyRow
                      depth={1}
                      domain="default"
                      kind="scheme"
                      label={scheme.title}
                      meta={countLabel(schemeClasses.length, "class", "classes")}
                      description={scheme.description ?? ""}
                      onSelect={() => toggle(scheme.id)}
                      data-testid={`hierarchy-node-${scheme.id}`}
                    />
                    {schemeOpen &&
                      schemeClasses.map((cls) => (
                        <HierarchyRow
                          key={cls.id}
                          depth={2}
                          domain="default"
                          kind="class"
                          label={cls.title}
                          description={cls.description ?? ""}
                          selected={selectedClassId === cls.id}
                          onSelect={() => handleSelectClass(cls.id)}
                          data-testid={`hierarchy-node-${cls.id}`}
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

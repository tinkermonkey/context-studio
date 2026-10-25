import { useEffect, useRef } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Panel } from "@tinkermonkey/heimdall-ui";
import { HierarchyTree } from "@/components/ontology/HierarchyTree";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { SMALL_SET_LIMIT } from "@/api/config";
import { entityPath } from "@/lib/entityPaths";

interface EntityNavigatorProps {
  /** The node to highlight (the open page's entity, or its nearest node in the tree). */
  selectedId?: string;
  /** Ancestors of the selected node, opened so it is visible. */
  expandIds: string[];
}

/**
 * The knowledge-graph tree beside an entity page (taxonomy → scheme → class).
 * Choosing a node opens its page; the tree opens to and highlights the
 * current one, scrolling it into view once its row has loaded.
 */
export function EntityNavigator({ selectedId, expandIds }: EntityNavigatorProps) {
  const navigate = useNavigate();
  const treeRef = useRef<HTMLDivElement>(null);
  const {
    data: taxonomies,
    isLoading: taxonomiesLoading,
    error,
  } = useTaxonomies({
    limit: SMALL_SET_LIMIT,
  });
  const { data: schemes, isLoading: schemesLoading } = useSchemes(undefined, {
    limit: SMALL_SET_LIMIT,
  });

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

  return (
    <nav aria-label="Navigator" data-testid="entity-navigator">
      <Panel title="Navigator" noPadding>
        <div ref={treeRef} className="entity-navigator__tree">
          <HierarchyTree
            taxonomies={taxonomies?.items}
            schemes={schemes?.items}
            loading={taxonomiesLoading || schemesLoading}
            error={error}
            selectedId={selectedId}
            expandIds={expandIds}
            compact
            onSelectNode={(kind, id) => navigate({ to: entityPath(kind, id) })}
          />
        </div>
      </Panel>
    </nav>
  );
}

import { useState, useMemo } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

export interface HierarchyTreeProps {
  classes?: ClassResponse[];
  loading?: boolean;
  error?: Error | null;
  onNodeSelect?: (nodeId: string) => void;
  maxDepth?: number;
}

interface TreeNode {
  class: ClassResponse;
  children: TreeNode[];
}

function buildTree(classes: ClassResponse[]): TreeNode[] {
  const nodeMap = new Map<string, TreeNode>();

  classes.forEach((cls) => {
    nodeMap.set(cls.id, { class: cls, children: [] });
  });

  const roots: TreeNode[] = [];
  classes.forEach((cls) => {
    const node = nodeMap.get(cls.id)!;
    if (cls.parent_class_id && nodeMap.has(cls.parent_class_id)) {
      nodeMap.get(cls.parent_class_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  roots.sort((a, b) => a.class.title.localeCompare(b.class.title));
  return roots;
}

interface TreeNodeRendererProps {
  node: TreeNode;
  expandedNodeIds: Set<string>;
  onToggleExpanded: (nodeId: string) => void;
  onNodeSelect?: (nodeId: string) => void;
  depth: number;
  maxDepth: number;
}

function TreeNodeRenderer({
  node,
  expandedNodeIds,
  onToggleExpanded,
  onNodeSelect,
  depth,
  maxDepth,
}: TreeNodeRendererProps) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedNodeIds.has(node.class.id);
  const canExpand = hasChildren && depth < maxDepth;

  return (
    <div key={node.class.id} className="flex flex-col">
      <div className="kg-row">
        <div className="kg-cell kg-cell-l" data-depth={depth + 1}>
          {canExpand && (
            <button
              type="button"
              onClick={() => onToggleExpanded(node.class.id)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "20px",
                height: "20px",
                padding: 0,
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "var(--canvas-fg-3)",
                marginRight: "4px",
                flexShrink: 0,
              }}
              aria-label={isExpanded ? "Collapse" : "Expand"}
            >
              {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>
          )}
          {!canExpand && <div style={{ width: "24px", flexShrink: 0 }} />}

          <div
            className="kg-node"
            data-testid={`hierarchy-node-${node.class.id}`}
            data-domain={node.class.concept_scheme_id}
            onClick={() => onNodeSelect?.(node.class.id)}
            style={{
              flex: 1,
              cursor: onNodeSelect ? "pointer" : "default",
            }}
          >
            <div className="swatch" />
            <span style={{ flexGrow: 1 }}>{node.class.title}</span>
            {hasChildren && <span className="badge-tiny">{node.children.length}</span>}
          </div>
        </div>
      </div>

      {canExpand && isExpanded && (
        <div>
          {node.children.map((child) => (
            <TreeNodeRenderer
              key={child.class.id}
              node={child}
              expandedNodeIds={expandedNodeIds}
              onToggleExpanded={onToggleExpanded}
              onNodeSelect={onNodeSelect}
              depth={depth + 1}
              maxDepth={maxDepth}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function HierarchyTree({
  classes,
  loading = false,
  error = null,
  onNodeSelect,
  maxDepth = 5,
}: HierarchyTreeProps) {
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());

  const rootNodes = useMemo(() => {
    if (!classes || classes.length === 0) return [];
    return buildTree(classes);
  }, [classes]);

  const handleToggleExpanded = (nodeId: string) => {
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  if (error) {
    return <EmptyState title="Error" description={error.message || "Failed to load class hierarchy"} variant="compact" />;
  }

  if (loading) {
    return (
      <div className="stack">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton
            key={i}
            height="28px"
            style={{
              borderRadius: "var(--radius-md, 6px)",
              marginLeft: `${(i % 3) * 20}px`,
            }}
          />
        ))}
      </div>
    );
  }

  if (!classes || classes.length === 0) {
    return <EmptyState title="No classes found" variant="compact" />;
  }

  return (
    <div className="kg-tree">
      {rootNodes.map((node) => (
        <TreeNodeRenderer
          key={node.class.id}
          node={node}
          expandedNodeIds={expandedNodeIds}
          onToggleExpanded={handleToggleExpanded}
          onNodeSelect={onNodeSelect}
          depth={0}
          maxDepth={maxDepth}
        />
      ))}
    </div>
  );
}

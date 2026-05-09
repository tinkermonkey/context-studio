import { useState, useMemo } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";
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

function getDomainFromClass(cls: ClassResponse): "life" | "climate" | "software" | undefined {
  if (cls.taxonomy_id?.includes("life")) return "life";
  if (cls.taxonomy_id?.includes("climate")) return "climate";
  if (cls.taxonomy_id?.includes("software")) return "software";
  return undefined;
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
  const domain = getDomainFromClass(node.class);
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedNodeIds.has(node.class.id);
  const canExpand = hasChildren && depth < maxDepth;

  return (
    <div key={node.class.id} style={{ display: "flex", flexDirection: "column" }}>
      <div
        className="hierarchy-row"
        style={{
          display: "flex",
          alignItems: "center",
          paddingLeft: `${depth * 16}px`,
          paddingTop: "4px",
          paddingBottom: "4px",
        }}
      >
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
            }}
            aria-label={isExpanded ? "Collapse" : "Expand"}
          >
            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </button>
        )}
        {!canExpand && <div style={{ width: "20px" }} />}

        <div
          className="kg-node hierarchy-node"
          data-domain={domain}
          data-testid={`hierarchy-node-${node.class.id}`}
          onClick={() => onNodeSelect?.(node.class.id)}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 8px",
            marginLeft: "4px",
            borderRadius: "4px",
            border: "1px solid var(--canvas-bd-2)",
            background: "var(--canvas-bg-2)",
            cursor: onNodeSelect ? "pointer" : "default",
            transition: "background 0.1s, border-color 0.1s",
          }}
          onMouseEnter={(e) => {
            if (onNodeSelect) {
              const el = e.currentTarget as HTMLElement;
              el.style.background = "var(--canvas-card)";
              el.style.borderColor = "var(--accent-cyan-deep)";
            }
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget as HTMLElement;
            el.style.background = "var(--canvas-bg-2)";
            el.style.borderColor = "var(--canvas-bd-2)";
          }}
        >
          <div
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: getDomainColor(domain),
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg)", flexGrow: 1 }}>
            {node.class.title}
          </span>
          {hasChildren && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}>
              {node.children.length}
            </span>
          )}
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

function getDomainColor(domain?: "life" | "climate" | "software"): string {
  switch (domain) {
    case "life":
      return "var(--dom-life, #10b981)";
    case "climate":
      return "var(--dom-climate, #06b6d4)";
    case "software":
      return "var(--dom-software, #f59e0b)";
    default:
      return "var(--canvas-fg-3)";
  }
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
    return (
      <div
        style={{
          padding: "var(--space-4)",
          borderRadius: "var(--radius-md, 6px)",
          background: "var(--canvas-bg-2)",
          color: "var(--rose-600, #e11d48)",
          fontSize: "var(--text-sm)",
        }}
      >
        {error.message || "Failed to load class hierarchy"}
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
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
    return (
      <div
        style={{
          padding: "var(--space-4)",
          borderRadius: "var(--radius-md, 6px)",
          background: "var(--canvas-bg-2)",
          color: "var(--canvas-fg-3)",
          fontSize: "var(--text-sm)",
        }}
      >
        No classes found
      </div>
    );
  }

  return (
    <div className="hierarchy-tree">
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

export function HierarchyTreeSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
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

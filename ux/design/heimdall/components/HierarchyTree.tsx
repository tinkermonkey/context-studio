interface HierarchyTreeProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

const HierarchyTree = React.forwardRef<HTMLDivElement, HierarchyTreeProps>(
  ({ className = "", children, ...props }, ref) => {
    const classNames = ["hierarchy-tree", className].filter(Boolean).join(" ");

    return (
      <div ref={ref} className={classNames} {...props}>
        {children}
      </div>
    );
  },
);

HierarchyTree.displayName = "HierarchyTree";

// --- Babel-standalone: expose runtime values to window ---
window.HierarchyTree = HierarchyTree;

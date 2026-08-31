interface SidebarItem {
  id: string;
  label: string;
  icon?: IconName;
  count?: number;
  children?: Array<{
    id: string;
    label: string;
    count?: number;
  }>;
}

interface SidebarSection {
  title: string;
  items: SidebarItem[];
}

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {
  sections: SidebarSection[];
  activeItemId?: string;
  collapsed?: boolean;
  onCollapse?: (collapsed: boolean) => void;
  onSelectItem?: (itemId: string) => void;
  /** Ids of parent items expanded on first render (uncontrolled). */
  defaultExpandedIds?: string[];
  /** Controlled expansion. When provided, the component reflects this set and
   *  reports changes via onExpandedChange instead of managing its own state. */
  expandedIds?: string[];
  onExpandedChange?: (ids: string[]) => void;
  /** Show the built-in collapse toggle. Ignored when `appTitle` is provided —
   *  in that case the toggle is rendered inside the AppTitle action slot. */
  showCollapseToggle?: boolean;
  /** Render an AppTitle as the sidebar header. The collapse toggle is wired
   *  into its `action` slot so the caret sits to the right of the title. */
  appTitle?: AppTitleProps;
  /** Optional content rendered at the bottom of the sidebar (e.g. user identity). */
  footer?: React.ReactNode;
}

const Sidebar = React.forwardRef<HTMLDivElement, SidebarProps>(
  (
    {
      sections,
      activeItemId,
      collapsed = false,
      onCollapse,
      onSelectItem,
      defaultExpandedIds,
      expandedIds,
      onExpandedChange,
      showCollapseToggle = true,
      appTitle,
      footer,
      className = "",
      ...props
    },
    ref,
  ) => {
    const isControlled = expandedIds !== undefined;
    const [internalExpanded, setInternalExpanded] = useState<Set<string>>(
      () => new Set(defaultExpandedIds),
    );
    const expandedItems = isControlled ? new Set(expandedIds) : internalExpanded;

    const toggleExpanded = (id: string) => {
      const next = new Set(expandedItems);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      if (!isControlled) {
        setInternalExpanded(next);
      }
      onExpandedChange?.(Array.from(next));
    };

    const classNames = ["sidebar", collapsed && "sidebar--collapsed", className]
      .filter(Boolean)
      .join(" ");

    const collapseButton = (
      <button
        type="button"
        className="sidebar__toggle"
        onClick={() => onCollapse?.(!collapsed)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <Icon name={collapsed ? "chevronRight" : "chevronLeft"} size={16} />
      </button>
    );

    return (
      <div ref={ref} className={classNames} {...props}>
        {appTitle ? (
          <>
            <AppTitle
              {...appTitle}
              collapsed={collapsed}
              action={collapsed ? appTitle.action : (appTitle.action ?? collapseButton)}
            />
            {collapsed && collapseButton}
          </>
        ) : (
          showCollapseToggle && collapseButton
        )}

        <nav className="sidebar__nav" aria-label="Sidebar navigation">
          {sections.map((section) => (
            <div key={section.title} className="sidebar__section">
              {!collapsed && <div className="sidebar__section-title">{section.title}</div>}
              <div className="sidebar__items">
                {section.items.map((item) => {
                  const hasChildren = item.children && item.children.length > 0;
                  const isExpanded = expandedItems.has(item.id);
                  const isActive = activeItemId === item.id;

                  return (
                    <React.Fragment key={item.id}>
                      <button
                        type="button"
                        className={`sidebar__item ${isActive ? "sidebar__item--active" : ""}`}
                        onClick={() => {
                          if (hasChildren) {
                            toggleExpanded(item.id);
                          } else {
                            onSelectItem?.(item.id);
                          }
                        }}
                        title={collapsed ? item.label : undefined}
                        aria-current={isActive ? "page" : undefined}
                        aria-expanded={hasChildren ? isExpanded : undefined}
                      >
                        {item.icon && (
                          <Icon name={item.icon} size={18} className="sidebar__item-icon" />
                        )}
                        {!collapsed && <span className="sidebar__item-label">{item.label}</span>}
                        {!collapsed && item.count !== undefined && (
                          <span className="sidebar__item-count">{item.count}</span>
                        )}
                        {!collapsed && hasChildren && (
                          <Icon
                            name="chevronRight"
                            size={14}
                            className={`sidebar__item-chevron ${isExpanded ? "sidebar__item-chevron--open" : ""}`}
                          />
                        )}
                      </button>

                      {!collapsed &&
                        hasChildren &&
                        isExpanded &&
                        item.children!.map((child) => (
                          <button
                            key={child.id}
                            type="button"
                            className={`sidebar__item sidebar__item--child ${activeItemId === child.id ? "sidebar__item--active" : ""}`}
                            onClick={() => onSelectItem?.(child.id)}
                            aria-current={activeItemId === child.id ? "page" : undefined}
                          >
                            <span className="sidebar__item-label">{child.label}</span>
                            {child.count !== undefined && (
                              <span className="sidebar__item-count">{child.count}</span>
                            )}
                          </button>
                        ))}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        {footer && <div className="sidebar__footer">{footer}</div>}
      </div>
    );
  },
);

Sidebar.displayName = "Sidebar";

// --- Babel-standalone: expose runtime values to window ---
window.Sidebar = Sidebar;

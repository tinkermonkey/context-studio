interface QuickAccessTileProps extends React.HTMLAttributes<HTMLButtonElement> {
  icon: IconName;
  title: string;
  description?: string;
}

const QuickAccessTile = React.forwardRef<HTMLButtonElement, QuickAccessTileProps>(
  ({ icon, title, description, className = "", ...props }, ref) => {
    const classNames = ["quick-access-tile", className].filter(Boolean).join(" ");

    return (
      <button
        ref={ref}
        type="button"
        className={classNames}
        data-testid="quick-access-tile"
        {...props}
      >
        <div className="quick-access-tile__icon">
          <Icon name={icon} size={16} />
        </div>
        <div className="quick-access-tile__body">
          <div className="quick-access-tile__title">{title}</div>
          {description && <div className="quick-access-tile__description">{description}</div>}
        </div>
        <Icon name="chevronRight" size={13} className="quick-access-tile__chev" />
      </button>
    );
  },
);

QuickAccessTile.displayName = "QuickAccessTile";

// --- Babel-standalone: expose runtime values to window ---
window.QuickAccessTile = QuickAccessTile;

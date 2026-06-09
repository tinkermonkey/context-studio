import { Button, Icon, type IconName } from "@tinkermonkey/heimdall-ui";
import { pluralize } from "./utils";

export interface BulkBarAction {
  id: string;
  label: string;
  icon?: IconName;
  danger?: boolean;
}

interface BulkBarProps {
  count: number;
  entityLabel: string;
  actions: BulkBarAction[];
  onAction: (actionId: string) => void;
  onClear: () => void;
}

export function BulkBar({ count, entityLabel, actions, onAction, onClear }: BulkBarProps) {
  if (count === 0) return null;

  return (
    <div className="csb-bar" role="toolbar" aria-label="Bulk actions" data-testid="bulk-bar">
      <div className="csb-bar__count">
        <span className="csb-bar__badge" aria-label={`${count} selected`}>
          {count}
        </span>
        {pluralize(entityLabel, count)} selected
      </div>

      {actions.length > 0 && (
        <>
          <div className="csb-bar__sep" role="separator" />
          <div className="csb-bar__actions">
            {actions.map((action) => (
              <Button
                key={action.id}
                variant={action.danger ? "danger" : "ghost"}
                size="sm"
                onClick={() => onAction(action.id)}
                data-testid={`bulk-action-${action.id}`}
              >
                {action.icon && <Icon name={action.icon} size={14} />}
                {action.label}
              </Button>
            ))}
          </div>
        </>
      )}

      <div className="csb-bar__sep" role="separator" />
      <Button
        variant="ghost"
        size="sm"
        icon
        onClick={onClear}
        aria-label="Clear selection"
        data-testid="bulk-bar-clear"
      >
        <Icon name="x" size={14} />
      </Button>
    </div>
  );
}

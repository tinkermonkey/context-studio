import { LucideIcon } from "lucide-react";
import { Button } from "@tinkermonkey/heimdall-ui";

interface ConfigTileProps {
  icon: LucideIcon;
  title: string;
  description: string;
  summary: React.ReactNode | string | number | null;
  testid: string;
  onEdit?: () => void;
  onNavigate?: () => void;
  isLoading?: boolean;
}

export function ConfigTile({
  icon: Icon,
  title,
  description,
  summary,
  testid,
  onEdit,
  onNavigate,
  isLoading,
}: ConfigTileProps) {
  const handleClick = () => {
    if (onNavigate) {
      onNavigate();
    } else if (onEdit) {
      onEdit();
    }
  };

  return (
    <div className="config-tile" data-testid={testid} role="region" aria-label={title}>
      <div className="head">
        <div className="icon">
          <Icon size={18} />
        </div>
        <div className="config-tile-content">
          <div className="title">{title}</div>
          <div className="desc">{description}</div>
        </div>
      </div>

      <div className="meta">{summary}</div>

      {(onEdit || onNavigate) && (
        <div className="config-tile-actions">
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              handleClick();
            }}
            disabled={isLoading}
            data-testid={`${testid}-button`}
            aria-label={`${onNavigate ? "Manage" : "Edit"} ${title}`}
          >
            {onNavigate ? "Manage" : "Edit"}
          </Button>
        </div>
      )}
    </div>
  );
}

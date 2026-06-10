import { VersionPill, Chip } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { components } from "@/api/types";
import "./ConfigurationList.css";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];

interface ConfigurationListProps {
  configurations: PipelineConfigurationResponse[];
  selectedId?: string;
  onSelect: (configId: string) => void;
  isLoading: boolean;
  error?: Error | null;
  onRetry?: () => void;
}

export function ConfigurationList({
  configurations,
  selectedId,
  onSelect,
  isLoading,
  error,
  onRetry,
}: ConfigurationListProps) {
  if (isLoading) {
    return (
      <div
        className="configuration-list"
        data-testid="configuration-list"
        role="listbox"
        aria-label="Configurations loading"
      >
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={`skeleton-${i}`} className="configuration-skeleton" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="configuration-list" data-testid="configuration-list">
        <ErrorBanner error={error} onRetry={onRetry} message="Failed to load configurations" />
      </div>
    );
  }

  if (configurations.length === 0) {
    return (
      <div className="configuration-list" data-testid="configuration-list">
        <EmptyState
          title="No configurations"
          description="No configurations found for this implementation."
          variant="compact"
        />
      </div>
    );
  }

  return (
    <div
      className="configuration-list"
      data-testid="configuration-list"
      role="listbox"
      aria-label="Configurations"
    >
      {configurations.map((config) => {
        const isSelected = config.id === selectedId;
        return (
          <button
            key={config.id}
            className={`configuration-item ${isSelected ? "selected" : ""}`}
            onClick={() => onSelect(config.id)}
            data-testid={`configuration-item-${config.config_ref}-${config.version}`}
            role="option"
            aria-selected={isSelected}
          >
            <div className="configuration-version">
              <VersionPill>{config.version}</VersionPill>
            </div>
            <span className="configuration-name">{config.name ?? config.config_ref}</span>
            {config.is_system && <Chip variant="neutral">system</Chip>}
            {isSelected && <div className="configuration-indicator" />}
          </button>
        );
      })}
    </div>
  );
}

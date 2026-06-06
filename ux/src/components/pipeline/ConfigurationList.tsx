import { useMemo } from "react";
import { VersionPill } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { components } from "@/api/types";
import "./ConfigurationList.css";

type ConfigurationResponse = components["schemas"]["ConfigurationResponse"];

interface ConfigurationListProps {
  configurations: ConfigurationResponse[];
  selectedId?: string;
  onSelect: (configRef: string, version?: number) => void;
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
  const groupedConfigs = useMemo(() => {
    const groups = new Map<string, ConfigurationResponse[]>();
    configurations.forEach((config) => {
      const existing = groups.get(config.config_ref) || [];
      groups.set(config.config_ref, [...existing, config].sort((a, b) => b.version - a.version));
    });
    return Array.from(groups.entries());
  }, [configurations]);

  // Find default configuration (usually the one with highest version for 'default' ref)
  const defaultConfig = useMemo(() => {
    const defaultGroup = groupedConfigs.find(([ref]) => ref === "default");
    if (defaultGroup && defaultGroup[1].length > 0) {
      return defaultGroup[1][0]; // First one is highest version due to sort
    }
    return null;
  }, [groupedConfigs]);

  if (isLoading) {
    return (
      <div
        className="configuration-list"
        data-testid="configuration-list"
        role="region"
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

  const isSelected = (config: ConfigurationResponse) => {
    if (!selectedId) return false;
    // selectedId format: "config_ref_vVersion" or just "config_ref"
    const parts = selectedId.split("_v");
    const selectedRef = parts[0];
    const selectedVersion = parts[1] ? parseInt(parts[1]) : undefined;
    return config.config_ref === selectedRef && (!selectedVersion || config.version === selectedVersion);
  };

  return (
    <div
      className="configuration-list"
      data-testid="configuration-list"
      role="region"
      aria-label="Configurations"
    >
      {groupedConfigs.map(([ref, configs]) => (
        <div key={ref} className="configuration-group">
          <div className="configuration-group-title">
            {defaultConfig?.config_ref === ref && (
              <span className="default-badge" title="Default configuration">
                Default
              </span>
            )}
            {ref}
          </div>
          {configs.map((config) => (
            <button
              key={`${config.config_ref}-${config.version}`}
              className={`configuration-item ${isSelected(config) ? "selected" : ""}`}
              onClick={() => onSelect(config.config_ref, config.version)}
              data-testid={`configuration-item-${config.config_ref}-${config.version}`}
              role="option"
              aria-selected={isSelected(config)}
            >
              <div className="configuration-version">
                <VersionPill>{config.version}</VersionPill>
              </div>
              {isSelected(config) && <div className="configuration-indicator" />}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

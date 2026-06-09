import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { components } from "@/api/types";
import "./ImplementationList.css";

type ImplementationResponse = components["schemas"]["ImplementationResponse"];

interface ImplementationListProps {
  implementations: ImplementationResponse[];
  selectedId?: string;
  onSelect: (implId: string) => void;
  isLoading: boolean;
  error?: Error | null;
  onRetry?: () => void;
}

export function ImplementationList({
  implementations,
  selectedId,
  onSelect,
  isLoading,
  error,
  onRetry,
}: ImplementationListProps) {
  if (isLoading) {
    return (
      <div
        className="implementation-list"
        data-testid="implementation-list"
        role="listbox"
        aria-label="Implementations loading"
      >
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={`skeleton-${i}`} className="implementation-skeleton" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="implementation-list" data-testid="implementation-list">
        <ErrorBanner error={error} onRetry={onRetry} message="Failed to load implementations" />
      </div>
    );
  }

  if (implementations.length === 0) {
    return (
      <div className="implementation-list" data-testid="implementation-list">
        <EmptyState
          title="No implementations"
          description="No implementations found for this pipeline type."
          variant="compact"
        />
      </div>
    );
  }

  return (
    <div
      className="implementation-list"
      data-testid="implementation-list"
      role="listbox"
      aria-label="Implementations"
    >
      {implementations.map((impl) => (
        <button
          key={impl.id}
          className={`implementation-item ${selectedId === impl.id ? "selected" : ""}`}
          onClick={() => onSelect(impl.id)}
          data-testid={`implementation-item-${impl.id}`}
          role="option"
          aria-selected={selectedId === impl.id}
        >
          <div className="implementation-id">{impl.id}</div>
          {selectedId === impl.id && <div className="implementation-indicator" />}
        </button>
      ))}
    </div>
  );
}

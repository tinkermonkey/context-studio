/**
 * SourceSelector Component
 *
 * Component for selecting which reference sources to include in unified search
 */

import React, { useEffect } from 'react';
import { Checkbox, Label, Card, Badge, Button } from 'flowbite-react';
import { CheckCircle, Circle, RefreshCw } from 'lucide-react';
import { useReferenceStore, useSourceState } from '@/store/referenceSlice';
import { useAvailableSources, useSourceStatus } from '@/api/hooks/unifiedReference/useUnifiedReference';
import { SOURCE_METADATA } from '@/api/types/unified';

interface SourceSelectorProps {
  showStatus?: boolean;
  compact?: boolean;
  onChange?: (selectedSources: string[]) => void;
}

export const SourceSelector: React.FC<SourceSelectorProps> = ({
  showStatus = true,
  compact = false,
  onChange,
}) => {
  const {
    selectedSources,
    toggleSource,
    setAllSources,
    resetSources,
  } = useReferenceStore();

  const { allSelected, noneSelected } = useSourceState();

  const {
    data: availableSources,
    isLoading: sourcesLoading,
    error: sourcesError,
  } = useAvailableSources();

  const {
    data: sourceStatus,
    isLoading: statusLoading,
    refetch: refetchStatus,
  } = useSourceStatus();

  // Initialize sources when available sources are loaded
  useEffect(() => {
    if (availableSources && selectedSources.length === 0) {
      setAllSources(availableSources);
    }
  }, [availableSources, selectedSources.length, setAllSources]);

  // Notify parent component of changes
  useEffect(() => {
    onChange?.(selectedSources);
  }, [selectedSources, onChange]);

  const handleSelectAll = () => {
    if (allSelected) {
      setAllSources([]);
    } else {
      setAllSources(availableSources || []);
    }
  };

  const handleReset = () => {
    resetSources();
  };

  const getSourceStatus = (sourceName: string) => {
    return sourceStatus?.find(status => status.name === sourceName);
  };

  const getSourceMeta = (sourceName: string) => {
    return SOURCE_METADATA[sourceName] || {
      label: sourceName,
      color: 'gray',
      description: '',
    };
  };

  const renderSourceItem = (source: string) => {
    const meta = getSourceMeta(source);
    const status = getSourceStatus(source);
    const isSelected = selectedSources.includes(source);
    const isAvailable = status?.available !== false;

    const colorClass = isSelected
      ? `border-${meta.color}-500 bg-${meta.color}-50`
      : 'border-gray-200 hover:border-gray-300';

    return (
      <div
        key={source}
        className={`
          p-3 rounded-lg border-2 transition-all cursor-pointer
          ${colorClass}
          ${!isAvailable ? 'opacity-50' : ''}
        `}
        onClick={() => isAvailable && toggleSource(source)}
      >
        <div className="flex items-start gap-2">
          <div className="flex items-center">
            {isSelected ? (
              <CheckCircle className={`w-5 h-5 text-${meta.color}-600`} />
            ) : (
              <Circle className="w-5 h-5 text-gray-400" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Label className={`text-${meta.color}-600 font-medium`}>
                {meta.label}
              </Label>

              {showStatus && status && (
                <Badge
                  color={isAvailable ? "success" : "failure"}
                  size="xs"
                >
                  {isAvailable ? "Online" : "Offline"}
                </Badge>
              )}
            </div>

            {!compact && (
              <>
                <p className="text-xs text-gray-500 mt-1">
                  {meta.description}
                </p>

                {showStatus && status && (
                  <div className="text-xs text-gray-400 mt-1">
                    {isAvailable ? (
                      <span>Response: {status.response_time_ms}ms</span>
                    ) : (
                      <span className="text-red-500">
                        {status.error_message || 'Unavailable'}
                      </span>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (sourcesLoading) {
    return (
      <Card>
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </Card>
    );
  }

  if (sourcesError) {
    return (
      <Card>
        <div className="text-center py-4">
          <p className="text-red-600 mb-2">Failed to load sources</p>
          <Button size="sm" color="gray" onClick={() => window.location.reload()}>
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Reference Sources</h3>

          <div className="flex items-center gap-2">
            {showStatus && (
              <Button
                size="xs"
                color="gray"
                onClick={() => refetchStatus()}
                disabled={statusLoading}
              >
                <RefreshCw className={`w-3 h-3 ${statusLoading ? 'animate-spin' : ''}`} />
              </Button>
            )}

            <Button
              size="xs"
              color="gray"
              onClick={handleReset}
              disabled={!availableSources}
            >
              Reset
            </Button>

            <div className="flex items-center gap-2">
              <Checkbox
                id="select-all"
                checked={allSelected && !noneSelected}
                onChange={handleSelectAll}
                disabled={!availableSources}
              />
              <Label htmlFor="select-all">
                {allSelected ? 'Deselect All' : 'Select All'}
              </Label>
            </div>
          </div>
        </div>

        {/* Source Selection */}
        <div className={`grid gap-3 ${compact ? 'grid-cols-2' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'}`}>
          {availableSources?.map(renderSourceItem)}
        </div>

        {/* Summary */}
        <div className="flex items-center justify-between text-sm text-gray-600 pt-2 border-t">
          <span>{selectedSources.length} of {availableSources?.length || 0} sources selected</span>

          {showStatus && sourceStatus && (
            <span>
              {sourceStatus.filter(s => s.available).length} online
            </span>
          )}
        </div>
      </div>
    </Card>
  );
};

export default SourceSelector;
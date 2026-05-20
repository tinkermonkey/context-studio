import { TextInput as Input, Button } from "@tinkermonkey/heimdall-ui";
import { useState } from "react";
import { Loader2 } from "lucide-react";

import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useShortestPath } from "@/api/hooks/graph";
import { COPY } from "@/routes/app/graph/-copy";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

interface PathFinderProps {
  onNodeSelect: (nodeId: string) => void;
}

interface NodeTypeaheadProps {
  label: string;
  selectedNode: ClassResponse | null;
  onSelect: (node: ClassResponse) => void;
  onClear: () => void;
  allClasses: ClassResponse[];
  testIdPrefix: string;
}

const MIN_SEARCH_CHARS = 2;

function NodeTypeahead({
  label,
  selectedNode,
  onSelect,
  onClear,
  allClasses,
  testIdPrefix,
}: NodeTypeaheadProps) {
  const [search, setSearch] = useState("");
  const [showOptions, setShowOptions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const filteredClasses =
    search.length >= MIN_SEARCH_CHARS
      ? allClasses.filter(
          (cls) =>
            cls.title.toLowerCase().includes(search.toLowerCase()) ||
            cls.id.toLowerCase().includes(search.toLowerCase()),
        )
      : [];

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setShowOptions(true);
    setActiveIndex(-1);
  };

  const handleSelect = (cls: ClassResponse) => {
    onSelect(cls);
    setSearch("");
    setShowOptions(false);
    setActiveIndex(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showOptions || filteredClasses.length === 0) {
      if (e.key === "Escape") {
        setShowOptions(false);
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((prev) => (prev < filteredClasses.length - 1 ? prev + 1 : prev));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case "Enter":
        e.preventDefault();
        if (activeIndex >= 0) {
          handleSelect(filteredClasses[activeIndex]);
        }
        break;
      case "Escape":
        e.preventDefault();
        setShowOptions(false);
        setActiveIndex(-1);
        break;
    }
  };

  const handleOptionKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleSelect(filteredClasses[index]);
    }
  };

  return (
    <div className="entity-picker">
      <label className="form-group-label">{label}</label>
      {selectedNode ? (
        <div className="entity-picked">
          <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
            {selectedNode.id.slice(0, 12)}
          </span>
          <span>{selectedNode.title}</span>
          <button
            type="button"
            onClick={onClear}
            className="entity-clear"
            data-testid={`${testIdPrefix}-clear`}
            aria-label={`Clear ${label}`}
          >
            ✕
          </button>
        </div>
      ) : (
        <>
          <Input
            type="text"
            placeholder={COPY.PATH_FINDER_SEARCH_PLACEHOLDER}
            value={search}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setShowOptions(true)}
            data-testid={`${testIdPrefix}-input`}
          />
          {showOptions && filteredClasses.length > 0 && (
            <div className="entity-results">
              {filteredClasses.map((cls, index) => (
                <button
                  key={cls.id}
                  type="button"
                  className="entity-result"
                  onClick={() => handleSelect(cls)}
                  onKeyDown={(e) => handleOptionKeyDown(e, index)}
                  data-testid={`${testIdPrefix}-option-${cls.id}`}
                  aria-selected={activeIndex === index}
                  style={activeIndex === index ? { background: "var(--canvas-bg-2)" } : {}}
                >
                  <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
                    {cls.id.slice(0, 12)}
                  </span>
                  <span>{cls.title}</span>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function PathFinder({ onNodeSelect }: PathFinderProps) {
  const [sourceId, setSourceId] = useState<string>("");
  const [targetId, setTargetId] = useState<string>("");

  const { data: classesResponse } = useClasses();
  const allClasses = classesResponse?.items || [];

  const { data: pathResult, isPending: isLoading, error, mutate } = useShortestPath();

  const selectedSource = sourceId ? allClasses.find((c) => c.id === sourceId) : null;
  const selectedTarget = targetId ? allClasses.find((c) => c.id === targetId) : null;

  const handleFindPath = () => {
    if (sourceId && targetId) {
      mutate({ sourceId, targetId });
    }
  };

  const handleClearSource = () => {
    setSourceId("");
  };

  const handleClearTarget = () => {
    setTargetId("");
  };

  const renderNodeBadge = (nodeId: string, index: number) => (
    <button
      key={nodeId}
      onClick={() => onNodeSelect(nodeId)}
      className="node-badge"
      data-testid={`path-finder-result-node-${nodeId}`}
      type="button"
      aria-label={`Select node ${nodeId}`}
    >
      <span>{index + 1}.</span>
      <span>{nodeId}</span>
    </button>
  );

  const noPathFound = pathResult && pathResult.nodes.length === 0;
  const hasPath = pathResult && pathResult.nodes.length > 0;

  return (
    <div data-testid="path-finder" className="stack-lg">
      <NodeTypeahead
        label={COPY.SOURCE_NODE_LABEL}
        selectedNode={selectedSource || null}
        onSelect={(cls) => setSourceId(cls.id)}
        onClear={handleClearSource}
        allClasses={allClasses}
        testIdPrefix="path-finder-source"
      />

      <NodeTypeahead
        label={COPY.TARGET_NODE_LABEL}
        selectedNode={selectedTarget || null}
        onSelect={(cls) => setTargetId(cls.id)}
        onClear={handleClearTarget}
        allClasses={allClasses}
        testIdPrefix="path-finder-target"
      />

      <Button
        disabled={!sourceId || !targetId || isLoading}
        onClick={handleFindPath}
        data-testid="path-finder-find-button"
        className="btn-primary"
        aria-busy={isLoading}
      >
        {isLoading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            {COPY.FINDING_PATH_BUTTON}
          </>
        ) : (
          COPY.FIND_PATH_BUTTON
        )}
      </Button>

      {error && (
        <div
          data-testid="path-finder-error"
          style={{
            padding: "var(--space-3)",
            background: "var(--rose-50)",
            borderRadius: "var(--radius-sm)",
            color: "var(--rose-700)",
            fontSize: "var(--text-sm)",
            border: "1px solid var(--rose-200)",
          }}
        >
          <p style={{ margin: 0 }}>
            {error instanceof Error ? error.message : COPY.PATH_FINDER_ERROR_DEFAULT}
          </p>
        </div>
      )}

      {noPathFound && (
        <div
          data-testid="path-finder-empty-state"
          style={{
            padding: "var(--space-3)",
            background: "var(--canvas-bg-2)",
            borderRadius: "var(--radius-sm)",
            color: "var(--canvas-fg-3)",
            fontSize: "var(--text-sm)",
            textAlign: "center",
          }}
        >
          <p style={{ margin: 0 }}>{COPY.NO_PATH_FOUND}</p>
        </div>
      )}

      {hasPath && (
        <div data-testid="path-finder-result">
          <div
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--canvas-fg-3)",
              marginBottom: "var(--space-2)",
            }}
          >
            Distance: {pathResult.distance} edge{pathResult.distance !== 1 ? "s" : ""}
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--space-2)",
              alignItems: "center",
            }}
          >
            {pathResult.nodes.map((nodeId, index) => (
              <div
                key={nodeId}
                style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}
              >
                {index > 0 && (
                  <span style={{ color: "var(--canvas-fg-3)", fontSize: "var(--text-sm)" }}>→</span>
                )}
                {renderNodeBadge(nodeId, index)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

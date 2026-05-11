import { useState, useRef } from "react";
import { Loader2 } from "lucide-react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useShortestPath } from "@/api/hooks/graph";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];
type PathResultResponse = components["schemas"]["PathResultResponse"];

interface PathFinderProps {
  onNodeSelect: (nodeId: string) => void;
}

const MIN_SEARCH_CHARS = 2;

export function PathFinder({ onNodeSelect }: PathFinderProps) {
  const [sourceId, setSourceId] = useState<string>("");
  const [targetId, setTargetId] = useState<string>("");

  const [searchSource, setSearchSource] = useState("");
  const [showSourceOptions, setShowSourceOptions] = useState(false);
  const sourceInputRef = useRef<HTMLInputElement>(null);

  const [searchTarget, setSearchTarget] = useState("");
  const [showTargetOptions, setShowTargetOptions] = useState(false);
  const targetInputRef = useRef<HTMLInputElement>(null);

  const { data: classesResponse } = useClasses();
  const allClasses = classesResponse?.items || [];

  const { data: pathResult, isPending: isLoading, error } = useShortestPath(sourceId, targetId);

  const filteredSourceClasses = searchSource.length >= MIN_SEARCH_CHARS
    ? allClasses.filter(
        (cls) =>
          cls.title.toLowerCase().includes(searchSource.toLowerCase()) ||
          cls.id.toLowerCase().includes(searchSource.toLowerCase()),
      )
    : [];

  const filteredTargetClasses = searchTarget.length >= MIN_SEARCH_CHARS
    ? allClasses.filter(
        (cls) =>
          cls.title.toLowerCase().includes(searchTarget.toLowerCase()) ||
          cls.id.toLowerCase().includes(searchTarget.toLowerCase()),
      )
    : [];

  const selectedSource = sourceId ? allClasses.find((c) => c.id === sourceId) : null;
  const selectedTarget = targetId ? allClasses.find((c) => c.id === targetId) : null;

  const handleSelectSource = (cls: ClassResponse) => {
    setSourceId(cls.id);
    setSearchSource("");
    setShowSourceOptions(false);
  };

  const handleSelectTarget = (cls: ClassResponse) => {
    setTargetId(cls.id);
    setSearchTarget("");
    setShowTargetOptions(false);
  };

  const handleClearSource = () => {
    setSourceId("");
    setSearchSource("");
  };

  const handleClearTarget = () => {
    setTargetId("");
    setSearchTarget("");
  };

  const handleSourceInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchSource(e.target.value);
    setShowSourceOptions(true);
  };

  const handleTargetInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTarget(e.target.value);
    setShowTargetOptions(true);
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
      <span style={{ marginRight: "4px", fontSize: "var(--text-xs)" }}>{index + 1}.</span>
      <span>{nodeId}</span>
    </button>
  );

  const noPathFound = pathResult && pathResult.nodes.length === 0;
  const hasPath = pathResult && pathResult.nodes.length > 0;

  return (
    <div data-testid="path-finder" className="stack-lg">
      {/* Source Input */}
      <div style={{ position: "relative" }}>
        <label className="form-group-label">Source Node</label>
        {selectedSource ? (
          <div
            className="flex-row-center"
            style={{
              padding: "var(--space-2) var(--space-3)",
              background: "var(--canvas-bg-2)",
              borderRadius: "var(--radius-sm)",
              fontSize: "var(--text-sm)",
            }}
          >
            <span className="mono" style={{ flex: 1, fontSize: "var(--text-xs)" }}>
              {selectedSource.id.slice(0, 12)}
            </span>
            <span>{selectedSource.title}</span>
            <button
              type="button"
              onClick={handleClearSource}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                color: "var(--canvas-fg-3)",
              }}
              data-testid="path-finder-clear-source"
              aria-label="Clear source node"
            >
              ✕
            </button>
          </div>
        ) : (
          <>
            <Input
              ref={sourceInputRef}
              type="text"
              placeholder="Type to search (min 2 chars)"
              value={searchSource}
              onChange={handleSourceInputChange}
              onFocus={() => setShowSourceOptions(true)}
              data-testid="path-finder-source-input"
            />
            {showSourceOptions && filteredSourceClasses.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  right: 0,
                  background: "var(--canvas-bg)",
                  border: "1px solid var(--canvas-fg-4)",
                  borderRadius: "var(--radius-sm)",
                  marginTop: "4px",
                  zIndex: 10,
                  maxHeight: "200px",
                  overflowY: "auto",
                }}
              >
                {filteredSourceClasses.map((cls) => (
                  <button
                    key={cls.id}
                    type="button"
                    onClick={() => handleSelectSource(cls)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      padding: "var(--space-2) var(--space-3)",
                      width: "100%",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      fontSize: "var(--text-sm)",
                      color: "var(--canvas-fg)",
                      borderBottom: "1px solid var(--canvas-fg-4)",
                    }}
                    data-testid={`path-finder-source-option-${cls.id}`}
                  >
                    <span
                      className="mono"
                      style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}
                    >
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

      {/* Target Input */}
      <div style={{ position: "relative" }}>
        <label className="form-group-label">Target Node</label>
        {selectedTarget ? (
          <div
            className="flex-row-center"
            style={{
              padding: "var(--space-2) var(--space-3)",
              background: "var(--canvas-bg-2)",
              borderRadius: "var(--radius-sm)",
              fontSize: "var(--text-sm)",
            }}
          >
            <span className="mono" style={{ flex: 1, fontSize: "var(--text-xs)" }}>
              {selectedTarget.id.slice(0, 12)}
            </span>
            <span>{selectedTarget.title}</span>
            <button
              type="button"
              onClick={handleClearTarget}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                color: "var(--canvas-fg-3)",
              }}
              data-testid="path-finder-clear-target"
              aria-label="Clear target node"
            >
              ✕
            </button>
          </div>
        ) : (
          <>
            <Input
              ref={targetInputRef}
              type="text"
              placeholder="Type to search (min 2 chars)"
              value={searchTarget}
              onChange={handleTargetInputChange}
              onFocus={() => setShowTargetOptions(true)}
              data-testid="path-finder-target-input"
            />
            {showTargetOptions && filteredTargetClasses.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  right: 0,
                  background: "var(--canvas-bg)",
                  border: "1px solid var(--canvas-fg-4)",
                  borderRadius: "var(--radius-sm)",
                  marginTop: "4px",
                  zIndex: 10,
                  maxHeight: "200px",
                  overflowY: "auto",
                }}
              >
                {filteredTargetClasses.map((cls) => (
                  <button
                    key={cls.id}
                    type="button"
                    onClick={() => handleSelectTarget(cls)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      padding: "var(--space-2) var(--space-3)",
                      width: "100%",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      fontSize: "var(--text-sm)",
                      color: "var(--canvas-fg)",
                      borderBottom: "1px solid var(--canvas-fg-4)",
                    }}
                    data-testid={`path-finder-target-option-${cls.id}`}
                  >
                    <span
                      className="mono"
                      style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}
                    >
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

      {/* Find Path Button */}
      <Button
        disabled={!sourceId || !targetId || isLoading}
        onClick={() => {}}
        data-testid="path-finder-find-button"
        className="btn-primary"
        aria-busy={isLoading}
      >
        {isLoading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Finding path...
          </>
        ) : (
          "Find Path"
        )}
      </Button>

      {/* Results Section */}
      {isLoading && (
        <div style={{ textAlign: "center", padding: "var(--space-3)", color: "var(--canvas-fg-3)" }}>
          <p>Searching for path...</p>
        </div>
      )}

      {error && (
        <div
          style={{
            padding: "var(--space-3)",
            background: "var(--rose-50)",
            borderRadius: "var(--radius-sm)",
            color: "var(--rose-700)",
            fontSize: "var(--text-sm)",
            border: "1px solid var(--rose-200)",
          }}
          data-testid="path-finder-error"
        >
          <p style={{ margin: 0 }}>
            {error instanceof Error ? error.message : "Failed to find path"}
          </p>
        </div>
      )}

      {noPathFound && (
        <div
          style={{
            padding: "var(--space-3)",
            background: "var(--canvas-bg-2)",
            borderRadius: "var(--radius-sm)",
            color: "var(--canvas-fg-3)",
            fontSize: "var(--text-sm)",
            textAlign: "center",
          }}
          data-testid="path-finder-empty-state"
        >
          <p style={{ margin: 0 }}>No path found between these nodes</p>
        </div>
      )}

      {hasPath && (
        <div data-testid="path-finder-result">
          <div style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)", marginBottom: "var(--space-2)" }}>
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
              <div key={nodeId} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
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

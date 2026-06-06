import { useState } from "react";
import { Table, SegmentedControl } from "@tinkermonkey/heimdall-ui";
import type { SchemaExtractionOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";

interface SchemaExtractionReviewProps {
  outputSummary: SchemaExtractionOutputSummary | null;
}

type TabType = "classes" | "properties" | "relationships";

export function SchemaExtractionReview({
  outputSummary,
}: SchemaExtractionReviewProps) {
  const [activeTab, setActiveTab] = useState<TabType>("classes");
  const [selectedClasses, setSelectedClasses] = useState<(string | number)[]>([]);
  const [selectedProperties, setSelectedProperties] = useState<(string | number)[]>([]);
  const [selectedRelationships, setSelectedRelationships] = useState<(string | number)[]>(
    []
  );

  if (!outputSummary) {
    return (
      <div
        data-testid="schema-extraction-empty"
        style={{
          padding: "16px",
          color: "rgb(var(--canvas-fg-3))",
          fontSize: "12px",
        }}
      >
        No extraction candidates available
      </div>
    );
  }

  const classes = outputSummary.classes || [];
  const properties = outputSummary.properties || [];
  const relationships = outputSummary.relationships || [];

  const allClassesSelected =
    classes.length > 0 && selectedClasses.length === classes.length;
  const allPropertiesSelected =
    properties.length > 0 && selectedProperties.length === properties.length;
  const allRelationshipsSelected =
    relationships.length > 0 &&
    selectedRelationships.length === relationships.length;

  const handleSelectAllClasses = () => {
    if (allClassesSelected) {
      setSelectedClasses([]);
    } else {
      setSelectedClasses(classes.map((_, i) => `class-${i}`));
    }
  };

  const handleSelectAllProperties = () => {
    if (allPropertiesSelected) {
      setSelectedProperties([]);
    } else {
      setSelectedProperties(properties.map((_, i) => `prop-${i}`));
    }
  };

  const handleSelectAllRelationships = () => {
    if (allRelationshipsSelected) {
      setSelectedRelationships([]);
    } else {
      setSelectedRelationships(relationships.map((_, i) => `rel-${i}`));
    }
  };

  return (
    <div
      data-testid="schema-extraction-review"
      style={{ display: "flex", flexDirection: "column", gap: "12px" }}
    >
      <SegmentedControl
        value={activeTab}
        onChange={(value) => setActiveTab(value as TabType)}
        options={[
          { value: "classes", label: `Classes (${classes.length})` },
          { value: "properties", label: `Properties (${properties.length})` },
          {
            value: "relationships",
            label: `Relationships (${relationships.length})`,
          },
        ]}
      />

      {activeTab === "classes" && (
        <div data-testid="classes-table-container">
          {classes.length === 0 ? (
            <div
              style={{
                padding: "16px",
                color: "rgb(var(--canvas-fg-3))",
                fontSize: "12px",
              }}
            >
              No classes extracted
            </div>
          ) : (
            <Table
              columns={[
                {
                  key: "label" as const,
                  label: "Label",
                  render: (v) => (
                    <span style={{ fontWeight: 500 }}>{String(v)}</span>
                  ),
                },
                {
                  key: "description" as const,
                  label: "Description",
                  render: (v) => (
                    <span style={{ color: "rgb(var(--canvas-fg-3))" }}>
                      {String(v || "—")}
                    </span>
                  ),
                },
                {
                  key: "confidence" as const,
                  label: "Confidence",
                  width: "100px",
                  render: (v) => (
                    <span style={{ textAlign: "center" }}>
                      {(Number(v) * 100).toFixed(0)}%
                    </span>
                  ),
                },
              ]}
              data={classes}
              rowKey={(row, index) => `class-${index}`}
              selectable
              selectedRows={selectedClasses}
              onSelectRows={setSelectedClasses}
              emptyState={<span>No classes extracted</span>}
            />
          )}
          {classes.length > 0 && (
            <div
              style={{
                padding: "8px",
                borderTop: "1px solid rgb(var(--canvas-border))",
                display: "flex",
                alignItems: "center",
                fontSize: "12px",
              }}
            >
              <input
                type="checkbox"
                data-testid="schema-extraction-select-all-classes"
                checked={allClassesSelected}
                onChange={handleSelectAllClasses}
                aria-label="Select all classes"
                style={{ marginRight: "8px", cursor: "pointer" }}
              />
              <span>
                {selectedClasses.length === 0
                  ? "Select all"
                  : `${selectedClasses.length} of ${classes.length} selected`}
              </span>
            </div>
          )}
        </div>
      )}

      {activeTab === "properties" && (
        <div data-testid="properties-table-container">
          {properties.length === 0 ? (
            <div
              style={{
                padding: "16px",
                color: "rgb(var(--canvas-fg-3))",
                fontSize: "12px",
              }}
            >
              No properties extracted
            </div>
          ) : (
            <Table
              columns={[
                {
                  key: "label" as const,
                  label: "Label",
                  render: (v) => (
                    <span style={{ fontWeight: 500 }}>{String(v)}</span>
                  ),
                },
                {
                  key: "description" as const,
                  label: "Description",
                  render: (v) => (
                    <span style={{ color: "rgb(var(--canvas-fg-3))" }}>
                      {String(v || "—")}
                    </span>
                  ),
                },
                {
                  key: "confidence" as const,
                  label: "Confidence",
                  width: "100px",
                  render: (v) => (
                    <span style={{ textAlign: "center" }}>
                      {(Number(v) * 100).toFixed(0)}%
                    </span>
                  ),
                },
              ]}
              data={properties}
              rowKey={(row, index) => `prop-${index}`}
              selectable
              selectedRows={selectedProperties}
              onSelectRows={setSelectedProperties}
              emptyState={<span>No properties extracted</span>}
            />
          )}
          {properties.length > 0 && (
            <div
              style={{
                padding: "8px",
                borderTop: "1px solid rgb(var(--canvas-border))",
                display: "flex",
                alignItems: "center",
                fontSize: "12px",
              }}
            >
              <input
                type="checkbox"
                data-testid="schema-extraction-select-all-properties"
                checked={allPropertiesSelected}
                onChange={handleSelectAllProperties}
                aria-label="Select all properties"
                style={{ marginRight: "8px", cursor: "pointer" }}
              />
              <span>
                {selectedProperties.length === 0
                  ? "Select all"
                  : `${selectedProperties.length} of ${properties.length} selected`}
              </span>
            </div>
          )}
        </div>
      )}

      {activeTab === "relationships" && (
        <div data-testid="relationships-table-container">
          {relationships.length === 0 ? (
            <div
              style={{
                padding: "16px",
                color: "rgb(var(--canvas-fg-3))",
                fontSize: "12px",
              }}
            >
              No relationships extracted
            </div>
          ) : (
            <Table
              columns={[
                {
                  key: "source_label" as const,
                  label: "Source",
                  render: (v) => (
                    <span style={{ fontWeight: 500 }}>{String(v)}</span>
                  ),
                },
                {
                  key: "relationship_type" as const,
                  label: "Type",
                  render: (v) => (
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "12px",
                      }}
                    >
                      {String(v)}
                    </span>
                  ),
                },
                {
                  key: "target_label" as const,
                  label: "Target",
                  render: (v) => (
                    <span style={{ fontWeight: 500 }}>{String(v)}</span>
                  ),
                },
                {
                  key: "confidence" as const,
                  label: "Confidence",
                  width: "100px",
                  render: (v) => (
                    <span style={{ textAlign: "center" }}>
                      {(Number(v) * 100).toFixed(0)}%
                    </span>
                  ),
                },
              ]}
              data={relationships}
              rowKey={(row, index) => `rel-${index}`}
              selectable
              selectedRows={selectedRelationships}
              onSelectRows={setSelectedRelationships}
              emptyState={<span>No relationships extracted</span>}
            />
          )}
          {relationships.length > 0 && (
            <div
              style={{
                padding: "8px",
                borderTop: "1px solid rgb(var(--canvas-border))",
                display: "flex",
                alignItems: "center",
                fontSize: "12px",
              }}
            >
              <input
                type="checkbox"
                data-testid="schema-extraction-select-all-relationships"
                checked={allRelationshipsSelected}
                onChange={handleSelectAllRelationships}
                aria-label="Select all relationships"
                style={{ marginRight: "8px", cursor: "pointer" }}
              />
              <span>
                {selectedRelationships.length === 0
                  ? "Select all"
                  : `${selectedRelationships.length} of ${relationships.length} selected`}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

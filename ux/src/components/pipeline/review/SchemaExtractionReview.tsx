import { useState } from "react";
import { Table, SegmentedControl } from "@tinkermonkey/heimdall-ui";
import type { SchemaExtractionOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";
import "./ReviewComponents.css";

interface SchemaExtractionReviewProps {
  outputSummary: SchemaExtractionOutputSummary | null;
  selectedClasses?: (string | number)[];
  onSelectClasses?: (selected: (string | number)[]) => void;
  selectedProperties?: (string | number)[];
  onSelectProperties?: (selected: (string | number)[]) => void;
  selectedRelationships?: (string | number)[];
  onSelectRelationships?: (selected: (string | number)[]) => void;
}

type TabType = "classes" | "properties" | "relationships";

export function SchemaExtractionReview({
  outputSummary,
  selectedClasses: externalSelectedClasses,
  onSelectClasses: externalOnSelectClasses,
  selectedProperties: externalSelectedProperties,
  onSelectProperties: externalOnSelectProperties,
  selectedRelationships: externalSelectedRelationships,
  onSelectRelationships: externalOnSelectRelationships,
}: SchemaExtractionReviewProps) {
  const [activeTab, setActiveTab] = useState<TabType>("classes");
  const [internalSelectedClasses, setInternalSelectedClasses] = useState<(string | number)[]>([]);
  const [internalSelectedProperties, setInternalSelectedProperties] = useState<(string | number)[]>([]);
  const [internalSelectedRelationships, setInternalSelectedRelationships] = useState<(string | number)[]>(
    []
  );

  // Use external state if provided, otherwise use internal state
  const selectedClasses = externalSelectedClasses ?? internalSelectedClasses;
  const setSelectedClasses = externalOnSelectClasses ?? setInternalSelectedClasses;

  const selectedProperties = externalSelectedProperties ?? internalSelectedProperties;
  const setSelectedProperties = externalOnSelectProperties ?? setInternalSelectedProperties;

  const selectedRelationships = externalSelectedRelationships ?? internalSelectedRelationships;
  const setSelectedRelationships = externalOnSelectRelationships ?? setInternalSelectedRelationships;

  if (!outputSummary) {
    return (
      <div
        data-testid="schema-extraction-empty"
        className="review-empty"
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
      className="schema-extraction-review"
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
        <div
          data-testid="classes-table-container"
          className="schema-table-container"
        >
          {classes.length === 0 ? (
            <div className="review-empty">
              No classes extracted
            </div>
          ) : (
            <Table
              columns={[
                {
                  key: "label" as const,
                  label: "Label",
                  render: (v) => (
                    <span className="table-cell-label">{String(v)}</span>
                  ),
                },
                {
                  key: "description" as const,
                  label: "Description",
                  render: (v) => (
                    <span className="table-cell-description">
                      {String(v || "—")}
                    </span>
                  ),
                },
                {
                  key: "confidence" as const,
                  label: "Confidence",
                  width: "100px",
                  render: (v) => (
                    <span className="table-cell-confidence">
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
            <div className="schema-select-all-footer">
              <input
                type="checkbox"
                data-testid="schema-extraction-select-all-classes"
                checked={allClassesSelected}
                onChange={handleSelectAllClasses}
                aria-label="Select all classes"
                className="schema-select-all-checkbox"
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
        <div
          data-testid="properties-table-container"
          className="schema-table-container"
        >
          {properties.length === 0 ? (
            <div className="review-empty">
              No properties extracted
            </div>
          ) : (
            <Table
              columns={[
                {
                  key: "label" as const,
                  label: "Label",
                  render: (v) => (
                    <span className="table-cell-label">{String(v)}</span>
                  ),
                },
                {
                  key: "description" as const,
                  label: "Description",
                  render: (v) => (
                    <span className="table-cell-description">
                      {String(v || "—")}
                    </span>
                  ),
                },
                {
                  key: "confidence" as const,
                  label: "Confidence",
                  width: "100px",
                  render: (v) => (
                    <span className="table-cell-confidence">
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
            <div className="schema-select-all-footer">
              <input
                type="checkbox"
                data-testid="schema-extraction-select-all-properties"
                checked={allPropertiesSelected}
                onChange={handleSelectAllProperties}
                aria-label="Select all properties"
                className="schema-select-all-checkbox"
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
        <div
          data-testid="relationships-table-container"
          className="schema-table-container"
        >
          {relationships.length === 0 ? (
            <div className="review-empty">
              No relationships extracted
            </div>
          ) : (
            <Table
              columns={[
                {
                  key: "source_label" as const,
                  label: "Source",
                  render: (v) => (
                    <span className="table-cell-label">{String(v)}</span>
                  ),
                },
                {
                  key: "relationship_type" as const,
                  label: "Type",
                  render: (v) => (
                    <span className="table-cell-mono">
                      {String(v)}
                    </span>
                  ),
                },
                {
                  key: "target_label" as const,
                  label: "Target",
                  render: (v) => (
                    <span className="table-cell-label">{String(v)}</span>
                  ),
                },
                {
                  key: "confidence" as const,
                  label: "Confidence",
                  width: "100px",
                  render: (v) => (
                    <span className="table-cell-confidence">
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
            <div className="schema-select-all-footer">
              <input
                type="checkbox"
                data-testid="schema-extraction-select-all-relationships"
                checked={allRelationshipsSelected}
                onChange={handleSelectAllRelationships}
                aria-label="Select all relationships"
                className="schema-select-all-checkbox"
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

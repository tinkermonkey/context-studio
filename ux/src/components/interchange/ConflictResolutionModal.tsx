/**
 * Conflict Resolution Modal
 *
 * Modal for resolving import conflicts grouped by match_kind
 */

import React from "react";
import { Modal, Button, Select, Badge } from "flowbite-react";
import {
  ImportConflict,
  ResolutionRecord,
  ResolutionKind,
} from "@/api/types/interchange";
import { ChevronDown, ChevronUp } from "lucide-react";

interface ConflictResolutionModalProps {
  isOpen: boolean;
  onClose: () => void;
  conflicts: ImportConflict[];
  newEntityCount: number;
  onCommit: (resolutions: ResolutionRecord[]) => void;
  isLoading?: boolean;
}

interface ConflictGrouped {
  [key: string]: ImportConflict[];
}

export function ConflictResolutionModal({
  isOpen,
  onClose,
  conflicts,
  newEntityCount,
  onCommit,
  isLoading = false,
}: ConflictResolutionModalProps) {
  const [resolutions, setResolutions] = React.useState<
    Map<string, ResolutionKind>
  >(new Map());
  const [expandedGroups, setExpandedGroups] = React.useState<Set<string>>(
    new Set(["external_reference", "uuid", "title"]),
  );

  // Group conflicts by match_kind
  const groupedConflicts = React.useMemo(() => {
    const grouped: ConflictGrouped = {
      external_reference: [],
      uuid: [],
      title: [],
    };

    conflicts.forEach((conflict) => {
      if (grouped[conflict.match_kind]) {
        grouped[conflict.match_kind].push(conflict);
      }
    });

    return grouped;
  }, [conflicts]);

  // Initialize resolutions with defaults
  React.useEffect(() => {
    const newResolutions = new Map<string, ResolutionKind>();
    Object.entries(groupedConflicts).forEach(([matchKind, group]) => {
      group.forEach((conflict) => {
        const key = `${matchKind}-${conflict.incoming.id}`;
        newResolutions.set(key, conflict.default_resolution);
      });
    });
    setResolutions(newResolutions);
  }, [conflicts]);

  const handleResolutionChange = (
    matchKind: string,
    conflictIndex: string,
    resolution: ResolutionKind,
  ) => {
    const key = `${matchKind}-${conflictIndex}`;
    const newResolutions = new Map(resolutions);
    newResolutions.set(key, resolution);
    setResolutions(newResolutions);
  };

  const handleApplyAll = (matchKind: string, resolution: ResolutionKind) => {
    const newResolutions = new Map(resolutions);
    groupedConflicts[matchKind as keyof typeof groupedConflicts]?.forEach(
      (conflict) => {
        const key = `${matchKind}-${conflict.incoming.id}`;
        newResolutions.set(key, resolution);
      },
    );
    setResolutions(newResolutions);
  };

  const toggleGroup = (matchKind: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(matchKind)) {
      newExpanded.delete(matchKind);
    } else {
      newExpanded.add(matchKind);
    }
    setExpandedGroups(newExpanded);
  };

  const handleCommit = () => {
    const resolutionRecords: ResolutionRecord[] = Array.from(
      resolutions.entries(),
    ).map(([key, resolution]) => {
      // Split on first occurrence of hyphen only, since UUIDs contain hyphens
      const firstHyphenIndex = key.indexOf("-");
      const matchKind = key.substring(0, firstHyphenIndex);
      const entityId = key.substring(firstHyphenIndex + 1);
      return {
        match_kind: matchKind as ImportConflict["match_kind"],
        entity_id: entityId,
        resolution_chosen: resolution,
      };
    });
    onCommit(resolutionRecords);
  };

  const getGroupDescription = (matchKind: string, count: number): string => {
    switch (matchKind) {
      case "external_reference":
        return `${count} item${count !== 1 ? "s" : ""} matched by external reference — these will be merged by default`;
      case "uuid":
        return `${count} item${count !== 1 ? "s" : ""} matched by UUID with no other overlap — please review`;
      case "title":
        return `${count} item${count !== 1 ? "s" : ""} matched by title alone — please review`;
      default:
        return "";
    }
  };

  return (
    <Modal
      show={isOpen}
      onClose={onClose}
      size="4xl"
      data-testid="interchange-conflict-resolution-modal"
    >
      <Modal.Header>Resolve Import Conflicts</Modal.Header>
      <Modal.Body className="max-h-96 overflow-y-auto">
        <div className="space-y-6">
          {/* External Reference group */}
          {groupedConflicts.external_reference.length > 0 && (
            <div className="rounded-lg border p-4">
              <div
                data-testid="interchange-conflict-group-external-reference"
                className="flex cursor-pointer items-center justify-between"
                onClick={() => toggleGroup("external_reference")}
              >
                <div>
                  <h4 className="font-semibold">External References</h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {getGroupDescription(
                      "external_reference",
                      groupedConflicts.external_reference.length,
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge color="blue">
                    {groupedConflicts.external_reference.length}
                  </Badge>
                  {expandedGroups.has("external_reference") ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </div>
              </div>

              {expandedGroups.has("external_reference") && (
                <div className="mt-4 space-y-3">
                  {groupedConflicts.external_reference.map((conflict, idx) => (
                    <ConflictRow
                      key={idx}
                      conflict={conflict}
                      conflictIndex={conflict.incoming.id}
                      resolution={
                        resolutions.get(
                          `external_reference-${conflict.incoming.id}`,
                        ) || conflict.default_resolution
                      }
                      onResolutionChange={(resolution) =>
                        handleResolutionChange(
                          "external_reference",
                          conflict.incoming.id,
                          resolution,
                        )
                      }
                    />
                  ))}
                  <div className="mt-3 flex gap-2 border-t pt-3">
                    <span className="text-sm text-gray-600">Apply to all:</span>
                    {["skip", "overwrite", "merge"].map((res) => (
                      <Button
                        key={res}
                        size="xs"
                        color="light"
                        data-testid={`interchange-conflict-apply-all-external_reference-${res}`}
                        onClick={() =>
                          handleApplyAll(
                            "external_reference",
                            res as ResolutionKind,
                          )
                        }
                      >
                        {res}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* UUID group */}
          {groupedConflicts.uuid.length > 0 && (
            <div className="rounded-lg border p-4">
              <div
                data-testid="interchange-conflict-group-uuid"
                className="flex cursor-pointer items-center justify-between"
                onClick={() => toggleGroup("uuid")}
              >
                <div>
                  <h4 className="font-semibold">UUID Matches</h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {getGroupDescription("uuid", groupedConflicts.uuid.length)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge color="yellow">{groupedConflicts.uuid.length}</Badge>
                  {expandedGroups.has("uuid") ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </div>
              </div>

              {expandedGroups.has("uuid") && (
                <div className="mt-4 space-y-3">
                  {groupedConflicts.uuid.map((conflict, idx) => (
                    <ConflictRow
                      key={idx}
                      conflict={conflict}
                      conflictIndex={conflict.incoming.id}
                      resolution={
                        resolutions.get(
                          `uuid-${conflict.incoming.id}`,
                        ) || conflict.default_resolution
                      }
                      onResolutionChange={(resolution) =>
                        handleResolutionChange(
                          "uuid",
                          conflict.incoming.id,
                          resolution,
                        )
                      }
                    />
                  ))}
                  <div className="mt-3 flex gap-2 border-t pt-3">
                    <span className="text-sm text-gray-600">Apply to all:</span>
                    {["skip", "overwrite", "merge"].map((res) => (
                      <Button
                        key={res}
                        size="xs"
                        color="light"
                        data-testid={`interchange-conflict-apply-all-uuid-${res}`}
                        onClick={() =>
                          handleApplyAll("uuid", res as ResolutionKind)
                        }
                      >
                        {res}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Title group */}
          {groupedConflicts.title.length > 0 && (
            <div className="rounded-lg border p-4">
              <div
                data-testid="interchange-conflict-group-title"
                className="flex cursor-pointer items-center justify-between"
                onClick={() => toggleGroup("title")}
              >
                <div>
                  <h4 className="font-semibold">Title Matches</h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {getGroupDescription(
                      "title",
                      groupedConflicts.title.length,
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge color="orange">{groupedConflicts.title.length}</Badge>
                  {expandedGroups.has("title") ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </div>
              </div>

              {expandedGroups.has("title") && (
                <div className="mt-4 space-y-3">
                  {groupedConflicts.title.map((conflict, idx) => (
                    <ConflictRow
                      key={idx}
                      conflict={conflict}
                      conflictIndex={conflict.incoming.id}
                      resolution={
                        resolutions.get(
                          `title-${conflict.incoming.id}`,
                        ) || conflict.default_resolution
                      }
                      onResolutionChange={(resolution) =>
                        handleResolutionChange(
                          "title",
                          conflict.incoming.id,
                          resolution,
                        )
                      }
                    />
                  ))}
                  <div className="mt-3 flex gap-2 border-t pt-3">
                    <span className="text-sm text-gray-600">Apply to all:</span>
                    {["skip", "overwrite", "merge"].map((res) => (
                      <Button
                        key={res}
                        size="xs"
                        color="light"
                        data-testid={`interchange-conflict-apply-all-title-${res}`}
                        onClick={() =>
                          handleApplyAll("title", res as ResolutionKind)
                        }
                      >
                        {res}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* New entities section */}
          {newEntityCount > 0 && (
            <div
              data-testid="interchange-conflict-group-create"
              className="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950"
            >
              <h4 className="font-semibold text-green-900 dark:text-green-100">
                New Concepts
              </h4>
              <p className="mt-2 text-sm text-green-700 dark:text-green-300">
                {newEntityCount} new entit{newEntityCount !== 1 ? "ies" : "y"}{" "}
                will be created
              </p>
            </div>
          )}
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button
          data-testid="interchange-conflict-cancel-button"
          color="gray"
          onClick={onClose}
          disabled={isLoading}
        >
          Close
        </Button>
        <Button
          data-testid="interchange-conflict-commit-button"
          onClick={handleCommit}
          disabled={isLoading}
          color="blue"
        >
          {isLoading ? "Committing..." : "Commit Import"}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

interface ConflictRowProps {
  conflict: ImportConflict;
  conflictIndex: string;
  resolution: ResolutionKind;
  onResolutionChange: (resolution: ResolutionKind) => void;
}

function ConflictRow({
  conflict,
  conflictIndex,
  resolution,
  onResolutionChange,
}: ConflictRowProps) {
  const title = conflict.incoming.title;
  const existingId = conflict.existing;

  return (
    <div
      data-testid={`interchange-conflict-row-${conflictIndex}`}
      className="flex items-center gap-3 rounded bg-gray-50 p-3 dark:bg-gray-900"
    >
      <div className="flex-1">
        <p className="text-sm font-medium">{title}</p>
        {existingId && (
          <p className="text-xs text-gray-600 dark:text-gray-400">
            Exists as: {existingId}
          </p>
        )}
      </div>
      <Select
        data-testid={`interchange-conflict-resolution-select-${conflictIndex}`}
        value={resolution}
        onChange={(e) => onResolutionChange(e.target.value as ResolutionKind)}
      >
        {conflict.available_resolutions.map((res) => (
          <option key={res} value={res}>
            {res}
          </option>
        ))}
      </Select>
    </div>
  );
}

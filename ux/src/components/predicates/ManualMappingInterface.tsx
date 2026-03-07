/**
 * Manual Mapping Interface Component
 *
 * Interface for manually searching and mapping external predicates to global predicates.
 * Supports US-3.2: Manually Map Reference Predicates
 */

import React, { useState } from "react";
import {
  Badge,
  Button,
  Card,
  Label,
  Select,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
  TextInput,
} from "flowbite-react";
import { Plus, Search, Trash2 } from "lucide-react";
import { useExternalPredicates, usePredicates } from "@/api/hooks/predicates";
import { useButterToast } from "@/hooks/useButterToast";

export interface ManualMappingInterfaceProps {
  globalPredicateId?: string;
  onMappingCreate?: (
    globalPredicateId: string,
    externalPredicateId: string,
    confidence: number,
  ) => void;
}

export const ManualMappingInterface: React.FC<ManualMappingInterfaceProps> = ({
  globalPredicateId: initialGlobalPredicateId,
  onMappingCreate,
}) => {
  const [globalPredicateId, setGlobalPredicateId] = useState<string>(
    initialGlobalPredicateId || "",
  );
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [confidence, setConfidence] = useState<number>(0.8);
  const [selectedMappings, setSelectedMappings] = useState<
    Array<{ externalPredicateId: string; confidence: number }>
  >([]);
  const toast = useButterToast();

  // Query global predicates
  const { data: globalPredicates, isLoading: loadingGlobal } = usePredicates();

  // Query external predicates with search
  const { data: externalPredicates, isLoading: loadingExternal } =
    useExternalPredicates({
      page: 1,
      page_size: 50,
      source: sourceFilter || undefined,
    });

  // Filter external predicates by search query
  const filteredExternalPredicates = React.useMemo(() => {
    if (!externalPredicates?.data) return [];
    if (!searchQuery.trim()) return externalPredicates.data;

    const query = searchQuery.toLowerCase();
    return externalPredicates.data.filter(
      (p) =>
        p.title.toLowerCase().includes(query) ||
        p.external_id.toLowerCase().includes(query),
    );
  }, [externalPredicates?.data, searchQuery]);

  const handleAddMapping = (externalPredicateId: string): void => {
    if (!globalPredicateId) {
      toast.warning("Please select a global predicate first");
      return;
    }

    // Check if already mapped
    if (
      selectedMappings.some(
        (m) => m.externalPredicateId === externalPredicateId,
      )
    ) {
      toast.warning("This predicate is already mapped");
      return;
    }

    setSelectedMappings([
      ...selectedMappings,
      { externalPredicateId, confidence },
    ]);
    toast.success("Mapping added (not yet saved)");
  };

  const handleRemoveMapping = (externalPredicateId: string): void => {
    setSelectedMappings(
      selectedMappings.filter(
        (m) => m.externalPredicateId !== externalPredicateId,
      ),
    );
  };

  const handleSaveMappings = () => {
    if (!globalPredicateId) {
      toast.warning("Please select a global predicate");
      return;
    }

    if (selectedMappings.length === 0) {
      toast.warning("Please add at least one mapping");
      return;
    }

    // Call the callback for each mapping
    if (onMappingCreate) {
      selectedMappings.forEach((mapping) => {
        onMappingCreate(
          globalPredicateId,
          mapping.externalPredicateId,
          mapping.confidence,
        );
      });
      toast.success(`Saved ${selectedMappings.length} mappings`);
      setSelectedMappings([]);
    } else {
      toast.error("Mapping creation not configured");
    }
  };

  // Get unique sources
  const availableSources = React.useMemo(() => {
    if (!externalPredicates?.data) return [];
    const sources = new Set(externalPredicates.data.map((p) => p.source));
    return Array.from(sources).sort();
  }, [externalPredicates?.data]);

  const selectedGlobalPredicate = globalPredicates?.data?.find(
    (p) => p.id === globalPredicateId,
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Manual Mapping</h3>
        {selectedMappings.length > 0 && (
          <Button size="sm" onClick={handleSaveMappings}>
            Save {selectedMappings.length} Mappings
          </Button>
        )}
      </div>

      {/* Global Predicate Selection */}
      <Card>
        <Label htmlFor="global-predicate" className="mb-2 block">
          Global Predicate <span className="text-red-500">*</span>
        </Label>
        <Select
          id="global-predicate"
          value={globalPredicateId}
          onChange={(e) => setGlobalPredicateId(e.target.value)}
          disabled={loadingGlobal}
        >
          <option value="">Select a global predicate</option>
          {globalPredicates?.data?.map((predicate) => (
            <option key={predicate.id} value={predicate.id}>
              {predicate.title}
            </option>
          ))}
        </Select>

        {selectedGlobalPredicate && (
          <div className="mt-3 rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
            <p className="font-medium text-gray-900 dark:text-white">
              {selectedGlobalPredicate.title}
            </p>
            {selectedGlobalPredicate.definition && (
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                {selectedGlobalPredicate.definition}
              </p>
            )}
          </div>
        )}
      </Card>

      {/* Mapping Confidence */}
      <Card>
        <Label htmlFor="confidence" className="mb-2 block">
          Mapping Confidence: {confidence.toFixed(2)}
        </Label>
        <input
          type="range"
          id="confidence"
          min="0"
          max="1"
          step="0.05"
          value={confidence}
          onChange={(e) => setConfidence(Number(e.target.value))}
          className="w-full"
        />
        <p className="mt-1 text-xs text-gray-500">
          Confidence level for the mapping (0.0 = low, 1.0 = high)
        </p>
      </Card>

      {/* Search External Predicates */}
      <Card>
        <h4 className="mb-4 text-base font-medium">
          Search External Predicates
        </h4>

        <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <Label htmlFor="search" className="mb-2 block">
              Search
            </Label>
            <TextInput
              id="search"
              placeholder="Search by title, ID, or definition..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              icon={Search}
            />
          </div>

          <div>
            <Label htmlFor="source-filter-manual" className="mb-2 block">
              Source
            </Label>
            <Select
              id="source-filter-manual"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="">All Sources</option>
              {availableSources.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto">
          {loadingExternal && (
            <div className="flex items-center justify-center py-8">
              <Spinner size="lg" />
            </div>
          )}

          {!loadingExternal && filteredExternalPredicates.length === 0 && (
            <div className="py-8 text-center text-gray-500">
              {searchQuery.trim()
                ? "No predicates match your search"
                : "No external predicates found"}
            </div>
          )}

          {!loadingExternal && filteredExternalPredicates.length > 0 && (
            <Table hoverable>
              <TableHead>
                <TableRow>
                  <TableHeadCell>Source</TableHeadCell>
                  <TableHeadCell>External ID</TableHeadCell>
                  <TableHeadCell>Title</TableHeadCell>
                  <TableHeadCell>
                    <span className="sr-only">Actions</span>
                  </TableHeadCell>
                </TableRow>
              </TableHead>
              <TableBody className="divide-y">
                {filteredExternalPredicates.map((predicate) => (
                  <TableRow
                    key={predicate.id}
                    className="bg-white dark:border-gray-700 dark:bg-gray-800"
                  >
                    <TableCell>
                      <Badge color="info" size="sm">
                        {predicate.source}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {predicate.external_id}
                    </TableCell>
                    <TableCell>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {predicate.title}
                        </p>
                        {predicate.definition && (
                          <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                            {predicate.definition.length > 100
                              ? `${predicate.definition.slice(0, 100)}...`
                              : predicate.definition}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="xs"
                        onClick={() => handleAddMapping(predicate.id)}
                        disabled={
                          !globalPredicateId ||
                          selectedMappings.some(
                            (m) => m.externalPredicateId === predicate.id,
                          )
                        }
                      >
                        <Plus className="h-3 w-3" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </Card>

      {/* Selected Mappings */}
      {selectedMappings.length > 0 && (
        <Card>
          <h4 className="mb-4 text-base font-medium">
            Selected Mappings ({selectedMappings.length})
          </h4>

          <div className="space-y-2">
            {selectedMappings.map((mapping) => {
              const predicate = externalPredicates?.data.find(
                (p) => p.id === mapping.externalPredicateId,
              );
              return (
                <div
                  key={mapping.externalPredicateId}
                  className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-700"
                >
                  <div className="flex-1">
                    {predicate && (
                      <>
                        <div className="mb-1 flex items-center gap-2">
                          <Badge color="info" size="sm">
                            {predicate.source}
                          </Badge>
                          <Badge color="gray" size="sm">
                            Confidence: {mapping.confidence.toFixed(2)}
                          </Badge>
                        </div>
                        <p className="font-medium text-gray-900 dark:text-white">
                          {predicate.title}
                        </p>
                      </>
                    )}
                  </div>
                  <Button
                    size="xs"
                    color="failure"
                    onClick={() =>
                      handleRemoveMapping(mapping.externalPredicateId)
                    }
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
};

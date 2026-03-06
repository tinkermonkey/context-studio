/**
 * Relevance Selection UI Component
 *
 * Interface for marking predicates as relevant or irrelevant.
 * Supports US-3.3: Mark Global Predicates as Relevant
 */

import React, { useState } from "react";
import { Badge, Button, Card, Select, Spinner, Table, TableBody, TableCell, TableHead, TableHeadCell, TableRow, TextInput, ToggleSwitch  } from "flowbite-react";;
import { Check, X, Search, Filter } from "lucide-react";
import { usePredicates } from "@/api/hooks/predicates";
import { useButterToast } from "@/hooks/useButterToast";

export interface RelevanceSelectionUIProps {
  onMarkRelevant?: (predicateId: string, isRelevant: boolean) => void;
}

type RelevanceFilter = "all" | "relevant" | "irrelevant" | "unrated";

export const RelevanceSelectionUI: React.FC<RelevanceSelectionUIProps> = ({
  onMarkRelevant,
}) => {
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [relevanceFilter, setRelevanceFilter] =
    useState<RelevanceFilter>("all");
  const [showOnlyUnrated, setShowOnlyUnrated] = useState<boolean>(false);
  const toast = useButterToast();

  // TODO: Add relevance status to predicates API
  // For now, we'll track relevance in local state
  const [relevanceMap, setRelevanceMap] = useState<
    Record<string, boolean | undefined>
  >({});

  // Query predicates
  const { data: predicates, isLoading } = usePredicates();

  const handleMarkRelevant = (predicateId: string, isRelevant: boolean) => {
    setRelevanceMap({
      ...relevanceMap,
      [predicateId]: isRelevant,
    });

    if (onMarkRelevant) {
      onMarkRelevant(predicateId, isRelevant);
    }

    toast.success(
      `Predicate marked as ${isRelevant ? "relevant" : "irrelevant"}`,
    );
  };

  // Filter predicates
  const filteredPredicates = React.useMemo(() => {
    if (!predicates?.data) return [];

    let filtered = predicates.data;

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.title.toLowerCase().includes(query) ||
          p.identifier?.toLowerCase().includes(query) ||
          p.definition?.toLowerCase().includes(query),
      );
    }

    // Apply relevance filter
    if (relevanceFilter !== "all") {
      filtered = filtered.filter((p) => {
        const relevance = relevanceMap[p.id];
        if (relevanceFilter === "unrated") return relevance === undefined;
        if (relevanceFilter === "relevant") return relevance === true;
        if (relevanceFilter === "irrelevant") return relevance === false;
        return true;
      });
    }

    // Apply unrated filter
    if (showOnlyUnrated) {
      filtered = filtered.filter((p) => relevanceMap[p.id] === undefined);
    }

    return filtered;
  }, [predicates, searchQuery, relevanceFilter, showOnlyUnrated, relevanceMap]);

  // Calculate statistics
  const stats = React.useMemo(() => {
    if (!predicates?.data) {
      return { relevant: 0, irrelevant: 0, unrated: 0, total: 0 };
    }

    const relevant = predicates.data.filter(
      (p) => relevanceMap[p.id] === true,
    ).length;
    const irrelevant = predicates.data.filter(
      (p) => relevanceMap[p.id] === false,
    ).length;
    const unrated = predicates.data.filter(
      (p) => relevanceMap[p.id] === undefined,
    ).length;

    return {
      relevant,
      irrelevant,
      unrated,
      total: predicates.data.length,
    };
  }, [predicates, relevanceMap]);

  const getRelevanceBadge = (predicateId: string) => {
    const relevance = relevanceMap[predicateId];
    if (relevance === true) {
      return (
        <Badge color="success" size="sm">
          Relevant
        </Badge>
      );
    } else if (relevance === false) {
      return (
        <Badge color="failure" size="sm">
          Irrelevant
        </Badge>
      );
    }
    return (
      <Badge color="gray" size="sm">
        Unrated
      </Badge>
    );
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Relevance Selection</h3>
      </div>

      {/* Statistics */}
      <Card>
        <div className="grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {stats.total}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Total
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.relevant}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Relevant
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.irrelevant}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Irrelevant
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">
              {stats.unrated}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Unrated
            </div>
          </div>
        </div>
      </Card>

      {/* Filters */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div>
          <TextInput
            placeholder="Search predicates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            icon={Search}
          />
        </div>

        <div>
          <Select
            value={relevanceFilter}
            onChange={(e) =>
              setRelevanceFilter(e.target.value as RelevanceFilter)
            }
          >
            <option value="all">All Predicates</option>
            <option value="relevant">Relevant Only</option>
            <option value="irrelevant">Irrelevant Only</option>
            <option value="unrated">Unrated Only</option>
          </Select>
        </div>

        <div className="flex items-center">
          <Filter className="mr-2 h-4 w-4 text-gray-600 dark:text-gray-400" />
          <ToggleSwitch
            checked={showOnlyUnrated}
            onChange={setShowOnlyUnrated}
            label="Show Only Unrated"
          />
        </div>
      </div>

      {/* Results Count */}
      <div className="text-sm text-gray-600 dark:text-gray-400">
        Showing {filteredPredicates.length} of {stats.total} predicates
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
          </div>
        ) : filteredPredicates.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            {searchQuery.trim()
              ? "No predicates match your search"
              : showOnlyUnrated
                ? "All predicates have been rated"
                : "No predicates found"}
          </div>
        ) : (
          <Table hoverable>
            <TableHead>
              <TableRow>
                <TableHeadCell>Status</TableHeadCell>
                <TableHeadCell>Identifier</TableHeadCell>
                <TableHeadCell>Title</TableHeadCell>
                <TableHeadCell>Definition</TableHeadCell>
                <TableHeadCell className="text-center">Actions</TableHeadCell>
              </TableRow>
            </TableHead>
            <TableBody className="divide-y">
              {filteredPredicates.map((predicate) => (
                <TableRow
                  key={predicate.id}
                  className="bg-white dark:border-gray-700 dark:bg-gray-800"
                >
                  <TableCell>{getRelevanceBadge(predicate.id)}</TableCell>
                  <TableCell className="font-mono text-sm">
                    {predicate.identifier || (
                      <span className="text-gray-400">—</span>
                    )}
                  </TableCell>
                  <TableCell className="font-medium text-gray-900 dark:text-white">
                    {predicate.title}
                  </TableCell>
                  <TableCell className="max-w-md truncate">
                    {predicate.definition || (
                      <span className="text-gray-400">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-center gap-2">
                      <Button
                        size="xs"
                        color="success"
                        onClick={() => handleMarkRelevant(predicate.id, true)}
                        disabled={relevanceMap[predicate.id] === true}
                      >
                        <Check className="h-3 w-3" />
                      </Button>
                      <Button
                        size="xs"
                        color="failure"
                        onClick={() => handleMarkRelevant(predicate.id, false)}
                        disabled={relevanceMap[predicate.id] === false}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
};

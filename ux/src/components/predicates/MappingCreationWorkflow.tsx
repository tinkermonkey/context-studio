/**
 * Mapping Creation Workflow Component
 *
 * Multi-step workflow to create global predicates from clusters.
 * Supports US-3.1: Create Global Predicate from Cluster
 */

import React, { useState } from "react";
import {
  Badge,
  Button,
  Card,
  Label,
  Progress,
  Spinner,
  TextInput,
  Textarea,
} from "flowbite-react";
import { ArrowLeft, ArrowRight, Check, X } from "lucide-react";
import {
  useCreatePredicate,
  useExternalPredicates,
} from "@/api/hooks/predicates";
import { useButterToast } from "@/hooks/useButterToast";
import type {
  PredicateOut,
  ExternalPredicateOut,
} from "@/api/services/predicates";

export interface MappingCreationWorkflowProps {
  predicateIds: string[];
  onComplete?: (predicate: PredicateOut) => void;
  onCancel?: () => void;
}

type Step = "review" | "create" | "confirm";

export const MappingCreationWorkflow: React.FC<
  MappingCreationWorkflowProps
> = ({ predicateIds, onComplete, onCancel }) => {
  const [step, setStep] = useState<Step>("review");
  const [title, setTitle] = useState<string>("");
  const [definition, setDefinition] = useState<string>("");
  const [identifier, setIdentifier] = useState<string>("");
  const [createdPredicate, setCreatedPredicate] = useState<PredicateOut | null>(
    null,
  );
  const toast = useButterToast();

  // Query external predicates for the cluster
  const { data: predicatesData, isLoading } = useExternalPredicates({
    page: 1,
    page_size: 100,
  });

  // Create predicate mutation
  const createMutation = useCreatePredicate({
    onSuccess: (predicate: PredicateOut) => {
      setCreatedPredicate(predicate);
      setStep("confirm");
      toast.success("Global predicate created successfully");
    },
    onError: (error: Error) => {
      toast.error(`Failed to create global predicate: ${error.message}`);
    },
  });

  // Filter predicates by IDs in the cluster
  const clusterPredicates = React.useMemo(() => {
    if (!predicatesData?.data) return [];
    return predicatesData.data.filter((p: ExternalPredicateOut) =>
      predicateIds.includes(p.id),
    );
  }, [predicatesData?.data, predicateIds]);

  // Auto-generate identifier from title
  const generateIdentifier = (title: string): string => {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
  };

  // Suggest title and definition based on cluster
  const suggestMetadata = () => {
    if (clusterPredicates.length === 0) return;

    // Use the most common words in titles
    const titles = clusterPredicates.map((p: ExternalPredicateOut) => p.title);
    // Simple heuristic: use the shortest title as the base
    const sortedTitles = [...titles].sort((a, b) => a.length - b.length);
    setTitle(sortedTitles[0] || "");

    // Combine definitions
    const definitions = clusterPredicates
      .map((p: ExternalPredicateOut) => p.definition)
      .filter(Boolean)
      .slice(0, 3);
    if (definitions.length > 0) {
      setDefinition(definitions.join(". "));
    }
  };

  React.useEffect(() => {
    if (clusterPredicates.length > 0 && !title && step === "review") {
      suggestMetadata();
    }
  }, [clusterPredicates, title, step]);

  // Update identifier when title changes
  React.useEffect(() => {
    if (title) {
      setIdentifier(generateIdentifier(title));
    }
  }, [title]);

  const handleNext = () => {
    if (step === "review") {
      setStep("create");
    } else if (step === "create") {
      // Validate form
      if (!title.trim()) {
        toast.warning("Please enter a title for the global predicate");
        return;
      }

      // Create the predicate
      createMutation.mutate({
        name: identifier || generateIdentifier(title.trim()),
        type: "relationship",
        title: title.trim(),
        definition: definition.trim() || "",
        identifier: identifier || undefined,
      });
    }
  };

  const handleBack = () => {
    if (step === "create") {
      setStep("review");
    } else if (step === "confirm" && createdPredicate) {
      setStep("create");
    }
  };

  const handleComplete = () => {
    if (createdPredicate && onComplete) {
      onComplete(createdPredicate);
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    }
  };

  const stepIndex = step === "review" ? 0 : step === "create" ? 1 : 2;
  const progressValue = ((stepIndex + 1) / 3) * 100;

  return (
    <div className="flex flex-col gap-4">
      {/* Progress Bar */}
      <div>
        <div className="mb-2 flex justify-between text-sm text-gray-600 dark:text-gray-400">
          <span>Step {stepIndex + 1} of 3</span>
          <span>{Math.round(progressValue)}% Complete</span>
        </div>
        <Progress progress={progressValue} size="sm" color="blue" />
      </div>

      {/* Step: Review Cluster */}
      {step === "review" && (
        <Card>
          <h4 className="mb-4 text-lg font-medium">
            Review Cluster Predicates
          </h4>

          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Spinner size="lg" />
            </div>
          )}

          {!isLoading && clusterPredicates.length === 0 && (
            <div className="py-8 text-center text-gray-500">
              No predicates found in this cluster
            </div>
          )}

          {!isLoading && clusterPredicates.length > 0 && (
            <>
              <div className="mb-4">
                <Badge color="info" size="lg">
                  {clusterPredicates.length} predicates in cluster
                </Badge>
              </div>

              <div className="max-h-96 space-y-2 overflow-y-auto">
                {clusterPredicates.map((predicate: ExternalPredicateOut) => (
                  <div
                    key={predicate.id}
                    className="rounded-lg border border-gray-200 p-3 dark:border-gray-700"
                  >
                    <div className="mb-1 flex items-center gap-2">
                      <Badge color="gray" size="sm">
                        {predicate.source}
                      </Badge>
                      <span className="font-mono text-xs text-gray-500">
                        {predicate.external_id}
                      </span>
                    </div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {predicate.title}
                    </p>
                    {predicate.definition && (
                      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                        {predicate.definition}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      )}

      {/* Step: Create Global Predicate */}
      {step === "create" && (
        <Card>
          <h4 className="mb-4 text-lg font-medium">Create Global Predicate</h4>

          <div className="space-y-4">
            <div>
              <Label htmlFor="title" className="mb-2 block">
                Title <span className="text-red-500">*</span>
              </Label>
              <TextInput
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter predicate title"
                required
              />
              <p className="mt-1 text-xs text-gray-500">
                A descriptive name for this predicate
              </p>
            </div>

            <div>
              <Label htmlFor="definition" className="mb-2 block">
                Definition
              </Label>
              <Textarea
                id="definition"
                value={definition}
                onChange={(e) => setDefinition(e.target.value)}
                placeholder="Enter predicate definition (optional)"
                rows={4}
              />
              <p className="mt-1 text-xs text-gray-500">
                A clear explanation of what this predicate means
              </p>
            </div>

            <div>
              <Label htmlFor="identifier" className="mb-2 block">
                Identifier
              </Label>
              <TextInput
                id="identifier"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="Auto-generated from title"
              />
              <p className="mt-1 text-xs text-gray-500">
                Unique identifier for API usage (auto-generated if not provided)
              </p>
            </div>

            <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                This global predicate will map to {clusterPredicates.length}{" "}
                external predicates from the cluster.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Step: Confirm */}
      {step === "confirm" && createdPredicate && (
        <Card>
          <div className="flex items-center justify-center py-6">
            <div className="text-center">
              <div className="mb-4 flex justify-center">
                <div className="rounded-full bg-green-100 p-3 dark:bg-green-900/30">
                  <Check className="h-8 w-8 text-green-600 dark:text-green-400" />
                </div>
              </div>
              <h4 className="mb-2 text-xl font-bold text-gray-900 dark:text-white">
                Global Predicate Created
              </h4>
              <p className="mb-4 text-gray-600 dark:text-gray-400">
                Successfully created "{createdPredicate.title}"
              </p>

              <div className="mx-auto max-w-md space-y-2 text-left">
                <div className="flex justify-between rounded-lg bg-gray-50 p-2 dark:bg-gray-700">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    ID:
                  </span>
                  <span className="font-mono text-sm text-gray-900 dark:text-white">
                    {createdPredicate.id}
                  </span>
                </div>
                <div className="flex justify-between rounded-lg bg-gray-50 p-2 dark:bg-gray-700">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Identifier:
                  </span>
                  <span className="font-mono text-sm text-gray-900 dark:text-white">
                    {createdPredicate.identifier}
                  </span>
                </div>
                <div className="flex justify-between rounded-lg bg-gray-50 p-2 dark:bg-gray-700">
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Mapped Predicates:
                  </span>
                  <span className="font-mono text-sm text-gray-900 dark:text-white">
                    {clusterPredicates.length}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Navigation Buttons */}
      <div className="flex justify-between">
        <Button
          color="light"
          onClick={step === "review" ? handleCancel : handleBack}
          disabled={createMutation.isPending}
        >
          {step === "review" ? (
            <>
              <X className="mr-2 h-4 w-4" />
              Cancel
            </>
          ) : (
            <>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </>
          )}
        </Button>

        <Button
          onClick={step === "confirm" ? handleComplete : handleNext}
          disabled={
            createMutation.isPending ||
            (step === "review" && clusterPredicates.length === 0)
          }
        >
          {createMutation.isPending ? (
            <>
              <Spinner size="sm" className="mr-2" />
              Creating...
            </>
          ) : step === "confirm" ? (
            <>
              <Check className="mr-2 h-4 w-4" />
              Complete
            </>
          ) : (
            <>
              Next
              <ArrowRight className="ml-2 h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
};

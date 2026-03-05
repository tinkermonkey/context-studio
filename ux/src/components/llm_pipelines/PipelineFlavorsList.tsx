import React, { useState } from "react";
import { Button, Spinner, Alert, Modal } from "flowbite-react";
import { Plus,  } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { usePipelineFlavors } from "@/api/hooks/pipelineFlavors";
import { useDeletePipelineFlavor } from "@/api/hooks/pipelineFlavors/usePipelineFlavorMutations";
import type {
  PipelineType,
  PipelineFlavor,
} from "@/api/services/pipelineFlavors";
import { PipelineTypes } from "./pipelineTypes";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";

export interface PipelineFlavorsListProps {
  pipelineType: PipelineType;
}

export const PipelineFlavorsList: React.FC<PipelineFlavorsListProps> = ({
  pipelineType,
}) => {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [flavorToDelete, setFlavorToDelete] = useState<PipelineFlavor | null>(
    null,
  );

  const queryClient = useQueryClient();

  const {
    data: flavorsResponse,
    isLoading,
    error,
  } = usePipelineFlavors({ pipeline: pipelineType });

  const flavors = flavorsResponse?.flavors || [];

  const deleteMutation = useDeletePipelineFlavor({
    onSuccess: () => {
      setShowDeleteModal(false);
      setFlavorToDelete(null);
      // Manually invalidate the exact query key used by usePipelineFlavors
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PIPELINE_FLAVORS, "list", {
          pipeline: pipelineType,
        }),
      });
    },
    onError: (error) => {
      console.error("Failed to delete flavor:", error);
      // Keep modal open on error so user can retry
    },
  });

  const handleDeleteClick = (flavor: PipelineFlavor) => {
    setFlavorToDelete(flavor);
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = () => {
    if (flavorToDelete) {
      deleteMutation.mutate(flavorToDelete.id);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
    setFlavorToDelete(null);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner size="lg" />
        <span className="ml-3">Loading pipeline flavors...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Alert color="failure">
        <span className="font-medium">Error loading pipeline flavors:</span>{" "}
        {error.message}
      </Alert>
    );
  }

  return (
    <div className="space-y-6" data-testid="pipeline-flavors-list">
      {/* Flavors Management */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {PipelineTypes.find((p) => p.value === pipelineType)?.label} Flavors
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Manage configuration variants for this pipeline type
          </p>
        </div>
        <Link
          to="/app/config/pipelines/$pipelineType/create"
          params={{ pipelineType: pipelineType }}
        >
          <Button color="blue" data-testid="pipeline-flavor-create-button">
            <Plus className="mr-2 h-4 w-4" />
            Create New Flavor
          </Button>
        </Link>
      </div>

      <div className="space-y-4" data-testid="pipeline-flavors-container">
        {flavors.map((flavor) => (
          <div
            key={flavor.id}
            data-testid={`pipeline-flavor-card-${flavor.id}`}
            className="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
          >
            <div className="flex items-center justify-between">
              <div>
                <h4
                  className="font-medium text-gray-900 dark:text-white"
                  data-testid={`pipeline-flavor-title-${flavor.id}`}
                >
                  {flavor.title}
                </h4>
                <p
                  className="text-sm text-gray-500 dark:text-gray-400"
                  data-testid={`pipeline-flavor-details-${flavor.id}`}
                >
                  Provider: {flavor.llm_provider} | Model: {flavor.llm_model} |
                  Version: {flavor.version}
                </p>
                <p
                  className="mt-1 text-sm text-gray-600 dark:text-gray-300"
                  data-testid={`pipeline-flavor-status-${flavor.id}`}
                >
                  {flavor.enabled ? "Enabled" : "Disabled"} | Created:{" "}
                  {new Date(flavor.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex gap-2">
                <Link
                  to="/app/config/pipelines/$pipelineType/edit/$flavorId"
                  params={{
                    pipelineType: pipelineType,
                    flavorId: flavor.id,
                  }}
                >
                  <Button
                    size="sm"
                    color="gray"
                    disabled={flavor.title === "Default"}
                    data-testid={`pipeline-flavor-edit-button-${flavor.id}`}
                    title={
                      flavor.title === "Default"
                        ? "The Default flavor cannot be edited or deleted."
                        : undefined
                    }
                  >
                    Edit
                  </Button>
                </Link>
                <Link
                  to="/app/config/pipelines/$pipelineType/test/$flavorId"
                  params={{
                    pipelineType: pipelineType,
                    flavorId: flavor.id,
                  }}
                >
                  <Button
                    size="sm"
                    color="blue"
                    data-testid={`pipeline-flavor-test-button-${flavor.id}`}
                  >
                    Test
                  </Button>
                </Link>
                <Button
                  size="sm"
                  color="yellow"
                  disabled={
                    flavor.title === "Default" || deleteMutation.isPending
                  }
                  onClick={() => handleDeleteClick(flavor)}
                  data-testid={`pipeline-flavor-delete-button-${flavor.id}`}
                  title={
                    flavor.title === "Default"
                      ? "The Default flavor cannot be edited or deleted."
                      : undefined
                  }
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Delete Confirmation Modal */}
      <Modal show={showDeleteModal} onClose={handleCancelDelete}>
        <div className="p-6" data-testid="pipeline-flavor-delete-modal">
          <h3 className="mb-4 text-lg font-medium text-gray-900 dark:text-white">
            Confirm Delete
          </h3>
          <p className="mb-6 text-base leading-relaxed text-gray-500 dark:text-gray-400">
            Are you sure you want to delete the flavor "{flavorToDelete?.title}
            "? This action cannot be undone.
          </p>
          {deleteMutation.isError && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 dark:bg-red-900/20">
              <p className="text-sm text-red-600 dark:text-red-400">
                Failed to delete flavor. Please try again.
              </p>
            </div>
          )}
          <div className="flex justify-end gap-4">
            <Button
              color="red"
              onClick={handleConfirmDelete}
              disabled={deleteMutation.isPending}
              data-testid="pipeline-flavor-delete-confirm-button"
            >
              {deleteMutation.isPending ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </Button>
            <Button
              color="gray"
              onClick={handleCancelDelete}
              disabled={deleteMutation.isPending}
              data-testid="pipeline-flavor-delete-cancel-button"
            >
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

import React from "react";
import { createColumnHelper } from "@tanstack/react-table";
import {
  Badge,
  Button,
  Checkbox,
  Modal,
  ModalBody,
  ModalHeader,
} from "flowbite-react";
import {
  Calendar,
  Database,
  FolderOpen,
  HardDrive,
  Hash,
  Layers,
  Plus,
} from "lucide-react";
import { BaseNodeTable } from "@/components/node_tables/node_table";
import { DatasetForm } from "@/components/forms/dataset_form";
import { AddExistingDatasetForm } from "@/components/forms/add_existing_dataset_form";
import {
  useDatasets,
  useDeleteDataset,
  useActivateDataset,
  useForgetDataset,
} from "@/api/hooks/datasets";
import type { DatasetResponse } from "@/api/services/datasets";

// Props interface
interface DatasetsTableProps {
  className?: string;
}

// Column helper for the dataset table
const columnHelper = createColumnHelper<DatasetResponse>();

// Define table columns
const columns = [
  columnHelper.display({
    id: "select",
    header: ({ table }) => {
      const { rows } = table.getRowModel();
      const selectedCount = rows.filter((row) => row.getIsSelected()).length;
      const isAllSelected = rows.length > 0 && selectedCount === rows.length;
      const isSomeSelected = selectedCount > 0 && selectedCount < rows.length;

      return (
        <Checkbox
          checked={isAllSelected}
          indeterminate={isSomeSelected}
          onChange={() => {
            if (isAllSelected || isSomeSelected) {
              // Deselect all visible rows
              rows.forEach((row) => row.toggleSelected(false));
            } else {
              // Select all visible rows
              rows.forEach((row) => row.toggleSelected(true));
            }
          }}
        />
      );
    },
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onChange={() => row.toggleSelected()}
      />
    ),
    size: 32,
  }),
  columnHelper.accessor("title", {
    header: "Dataset",
    cell: (info) => {
      const dataset = info.row.original;
      return (
        <div className="flex items-center space-x-3">
          <div className="flex-shrink-0">
            <Database className="h-5 w-5 text-gray-400" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {dataset.title}
              </span>
              {dataset.is_active && (
                <Badge color="success" size="sm">
                  Active
                </Badge>
              )}
            </div>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {dataset.filename}
            </p>
          </div>
        </div>
      );
    },
  }),
  columnHelper.accessor("filename", {
    header: "Filename",
    cell: (info) => (
      <div className="flex items-center space-x-2">
        <HardDrive className="h-4 w-4 text-gray-400" />
        <span className="font-mono text-sm text-gray-900 dark:text-white">
          {info.getValue()}
        </span>
      </div>
    ),
  }),
  columnHelper.accessor("created_at", {
    header: "Created",
    cell: (info) => {
      const dateValue = info.getValue();
      const dateStr = dateValue
        ? new Date(dateValue).toLocaleDateString()
        : "Unknown";
      return (
        <div className="flex items-center space-x-2">
          <Calendar className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-900 dark:text-white">
            {dateStr}
          </span>
        </div>
      );
    },
  }),
  columnHelper.accessor("metrics", {
    header: "Statistics",
    cell: (info) => {
      const metrics = info.getValue();
      if (!metrics)
        return <span className="text-sm text-gray-400">No stats</span>;

      return (
        <div className="space-y-1">
          <div className="flex items-center space-x-1 text-xs text-gray-600 dark:text-gray-400">
            <Layers className="h-3 w-3" />
            <span>{metrics.taxonomies_count} taxonomies</span>
          </div>
          <div className="flex items-center space-x-1 text-xs text-gray-600 dark:text-gray-400">
            <Database className="h-3 w-3" />
            <span>{metrics.concept_schemes_count} concept schemes</span>
          </div>
          <div className="flex items-center space-x-1 text-xs text-gray-600 dark:text-gray-400">
            <Hash className="h-3 w-3" />
            <span>{metrics.classes_count} classes</span>
          </div>
        </div>
      );
    },
  }),
];

// Custom datasets table component that extends BaseNodeTable with dataset-specific actions
export const DatasetsTable: React.FC<DatasetsTableProps> = ({
  className = "",
}) => {
  const { data: datasets = [], isLoading, error, refetch } = useDatasets();
  const deleteDatasetMutation = useDeleteDataset();
  const activateDatasetMutation = useActivateDataset();
  const forgetDatasetMutation = useForgetDataset();

  // Custom action modals
  const [showCreateModal, setShowCreateModal] = React.useState(false);
  const [showAddExistingModal, setShowAddExistingModal] = React.useState(false);
  const [showActivateModal, setShowActivateModal] = React.useState(false);
  const [showForgetModal, setShowForgetModal] = React.useState(false);
  const [selectedDatasetIds, setSelectedDatasetIds] = React.useState<string[]>(
    [],
  );
  const [datasetToActivate, setDatasetToActivate] =
    React.useState<DatasetResponse | null>(null);

  const handleDelete = async (ids: string[]) => {
    for (const id of ids) {
      await deleteDatasetMutation.mutateAsync(id);
    }
  };

  const handleSetActive = (dataset: DatasetResponse) => {
    // Don't show modal if dataset is already active
    if (dataset.is_active) return;

    setDatasetToActivate(dataset);
    setShowActivateModal(true);
  };

  const confirmActivate = async () => {
    if (datasetToActivate) {
      await activateDatasetMutation.mutateAsync(datasetToActivate.id);
    }
    setShowActivateModal(false);
    setDatasetToActivate(null);
  };

  const confirmForget = async () => {
    for (const id of selectedDatasetIds) {
      await forgetDatasetMutation.mutateAsync(id);
    }
    setShowForgetModal(false);
    setSelectedDatasetIds([]);
  };

  const handleForgetSelected = (
    selectedItems: DatasetResponse[],
    selectedIds: string[],
  ) => {
    setSelectedDatasetIds(selectedIds);
    setShowForgetModal(true);
  };

  const getSelectedDataset = () => {
    return datasetToActivate;
  };

  return (
    <div className={className}>
      <BaseNodeTable
        columns={columns}
        data={datasets}
        isLoading={isLoading}
        error={error}
        onRefetch={refetch}
        onDelete={handleDelete}
        createForm={() => <div />} // Disabled since we have custom buttons
        editForm={() => <div />} // Dummy edit form since we're using custom action
        typeName="Dataset"
        getId={(item: DatasetResponse) => item.id}
        searchEnabled={true}
        searchPlaceholder="Search datasets..."
        pageSizeOptions={[10, 20, 50]}
        defaultPageSize={20}
        buttonBar={
          <>
            <Button
              color="blue"
              size="sm"
              onClick={() => setShowCreateModal(true)}
              className="w-auto whitespace-nowrap"
            >
              <Plus className="mr-2 h-4 w-4" />
              Create New Dataset
            </Button>
            <Button
              color="light"
              size="sm"
              onClick={() => setShowAddExistingModal(true)}
              className="w-auto whitespace-nowrap"
            >
              <FolderOpen className="mr-2 h-4 w-4" />
              Add Dataset
            </Button>
          </>
        }
        customRowAction={{
          label: (dataset: DatasetResponse) =>
            dataset.is_active ? "Active" : "Set Active",
          onClick: handleSetActive,
          className: (dataset: DatasetResponse) =>
            dataset.is_active
              ? "cursor-default text-gray-400"
              : "cursor-pointer text-green-600 hover:underline",
          disabled: (dataset: DatasetResponse) => dataset.is_active || false,
        }}
        customBulkActions={[
          {
            label: "Forget Selected",
            onClick: handleForgetSelected,
            className: "text-orange-600 hover:bg-orange-50",
          },
        ]}
      />

      {/* Create Dataset Modal */}
      <Modal show={showCreateModal} onClose={() => setShowCreateModal(false)}>
        <ModalHeader>Create New Dataset</ModalHeader>
        <ModalBody>
          <DatasetForm onSuccess={() => setShowCreateModal(false)} />
        </ModalBody>
      </Modal>

      {/* Add Existing Dataset Modal */}
      <Modal
        show={showAddExistingModal}
        onClose={() => setShowAddExistingModal(false)}
      >
        <ModalHeader>Add Existing Dataset</ModalHeader>
        <ModalBody>
          <AddExistingDatasetForm
            onSuccess={() => setShowAddExistingModal(false)}
          />
        </ModalBody>
      </Modal>

      <Modal
        show={showActivateModal}
        onClose={() => {
          setShowActivateModal(false);
          setDatasetToActivate(null);
        }}
      >
        <ModalHeader>Activate Dataset</ModalHeader>
        <ModalBody>
          <div className="space-y-4">
            <p>
              Are you sure you want to activate the dataset{" "}
              <strong>"{getSelectedDataset()?.title}"</strong>?
            </p>
            <p className="text-sm text-gray-600">
              This will switch the active dataset and reload all data from the
              new dataset.
            </p>
            <div className="flex justify-end gap-2 pt-4">
              <Button
                color="gray"
                onClick={() => {
                  setShowActivateModal(false);
                  setDatasetToActivate(null);
                }}
              >
                Cancel
              </Button>
              <Button
                color="blue"
                onClick={confirmActivate}
                disabled={activateDatasetMutation.isPending}
              >
                {activateDatasetMutation.isPending
                  ? "Activating..."
                  : "Activate Dataset"}
              </Button>
            </div>
          </div>
        </ModalBody>
      </Modal>

      <Modal show={showForgetModal} onClose={() => setShowForgetModal(false)}>
        <ModalHeader>
          Forget Dataset{selectedDatasetIds.length > 1 ? "s" : ""}
        </ModalHeader>
        <ModalBody>
          <div className="space-y-4">
            <p>
              Are you sure you want to forget {selectedDatasetIds.length}{" "}
              dataset{selectedDatasetIds.length > 1 ? "s" : ""}?
            </p>
            <p className="text-sm text-gray-600">
              This will remove the dataset
              {selectedDatasetIds.length > 1 ? "s" : ""} from the inventory but
              leave the file{selectedDatasetIds.length > 1 ? "s" : ""} intact on
              disk. You can add {selectedDatasetIds.length > 1 ? "them" : "it"}{" "}
              back later using "Add Existing Dataset".
            </p>
            <div className="flex justify-end gap-2 pt-4">
              <Button color="gray" onClick={() => setShowForgetModal(false)}>
                Cancel
              </Button>
              <Button
                color="orange"
                onClick={confirmForget}
                disabled={forgetDatasetMutation.isPending}
              >
                {forgetDatasetMutation.isPending
                  ? "Forgetting..."
                  : `Forget Dataset${selectedDatasetIds.length > 1 ? "s" : ""}`}
              </Button>
            </div>
          </div>
        </ModalBody>
      </Modal>
    </div>
  );
};

export default DatasetsTable;

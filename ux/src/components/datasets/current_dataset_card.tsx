import React from "react";
import { Card, Spinner, Badge, Button } from "flowbite-react";
import {
  Calendar,
  Database,
  FileText,
  Hash,
  Activity,
  Settings,
  Clock,
  ChevronRight,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useActiveDataset } from "@/api/hooks/datasets/useDatasets";
import type { components } from "@/api/client/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

interface CurrentDatasetCardProps {
  className?: string;
}

export const CurrentDatasetCard: React.FC<CurrentDatasetCardProps> = ({
  className = "",
}) => {
  const { data: activeDataset, isLoading, error } = useActiveDataset();

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatFileSize = (filename: string) => {
    // This would ideally come from the API, but we can estimate or show filename for now
    return filename;
  };

  if (isLoading) {
    return (
      <Card className={`w-full ${className}`}>
        <div className="flex items-center justify-center py-8">
          <Spinner size="lg" />
          <span className="ml-3 text-sm">Loading current dataset...</span>
        </div>
      </Card>
    );
  }

  if (error || !activeDataset) {
    return (
      <Card className={`w-full ${className}`}>
        <div className="text-center py-8">
          <Database className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            No Active Dataset
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            {error ? "Failed to load dataset information" : "No dataset is currently active"}
          </p>
          <Link to="/app/datasets">
            <Button size="sm">
              Manage Datasets
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <Card className={`w-full ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="flex-shrink-0">
            <Database className="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {activeDataset.title}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center">
              <FileText className="h-4 w-4 mr-1" />
              {activeDataset.filename}
            </p>
          </div>
        </div>
        <Badge color="success" size="sm">
          Active
        </Badge>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 mt-6">
        <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
            {activeDataset.metrics.layers_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Layers</div>
        </div>
        <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">
            {activeDataset.metrics.domains_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Domains</div>
        </div>
        <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
            {activeDataset.metrics.terms_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Terms</div>
        </div>
        <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
            {activeDataset.metrics.relationships_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Relationships
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="space-y-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-600 dark:text-gray-400">
            <Hash className="h-4 w-4 mr-2" />
            Dataset ID
          </span>
          <span className="font-mono text-xs text-gray-900 dark:text-white">
            {activeDataset.id}
          </span>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-600 dark:text-gray-400">
            <Activity className="h-4 w-4 mr-2" />
            Schema Version
          </span>
          <Badge color="gray" size="sm">
            v{activeDataset.schema_version}
          </Badge>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-600 dark:text-gray-400">
            <Calendar className="h-4 w-4 mr-2" />
            Created
          </span>
          <span className="text-gray-900 dark:text-white">
            {formatDate(activeDataset.created_at)}
          </span>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-600 dark:text-gray-400">
            <Clock className="h-4 w-4 mr-2" />
            Last Accessed
          </span>
          <span className="text-gray-900 dark:text-white">
            {formatDate(activeDataset.last_accessed)}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex space-x-3 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
        <Link to="/app/datasets" className="flex-1">
          <Button size="sm" outline className="w-full">
            <Settings className="mr-2 h-4 w-4" />
            Explore Structure
          </Button>
        </Link>
        <Link to="/app" className="flex-1">
          <Button size="sm" className="w-full">
            <ChevronRight className="mr-2 h-4 w-4" />
            Explore Data
          </Button>
        </Link>
      </div>
    </Card>
  );
};

export default CurrentDatasetCard;

/**
 * Predicate Mapping Manager Component
 *
 * Main component for managing predicate mappings including:
 * - External predicate discovery
 * - Similarity search and visualization
 * - Cluster-based mapping creation
 * - Manual mapping interface
 * - Relevance selection
 */

import React, { useState } from "react";
import { Card, Tabs, Modal } from "flowbite-react";
import {
  HiDatabase,
  HiSearch,
  HiCollection,
  HiCog,
  HiPlusCircle,
  HiCheckCircle,
} from "react-icons/hi";
import { ExternalPredicatesTab } from "./ExternalPredicatesTab";
import { SimilaritySearchTab } from "./SimilaritySearchTab";
import { ClusterVisualizationTab } from "./ClusterVisualizationTab";
import { MappingConfigurationTab } from "./MappingConfigurationTab";
import { ManualMappingInterface } from "./ManualMappingInterface";
import { RelevanceSelectionUI } from "./RelevanceSelectionUI";
import { MappingCreationWorkflow } from "./MappingCreationWorkflow";
import type { PredicateOut } from "@/api/services/predicates";

export interface PredicateMappingManagerProps {
  className?: string;
}

export const PredicateMappingManager: React.FC<
  PredicateMappingManagerProps
> = ({ className }) => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [showWorkflowModal, setShowWorkflowModal] = useState<boolean>(false);
  const [selectedPredicateIds, setSelectedPredicateIds] = useState<string[]>([]);

  const handleClusterSelect = (predicateIds: string[]) => {
    setSelectedPredicateIds(predicateIds);
    setShowWorkflowModal(true);
  };

  const handleWorkflowComplete = (predicate: PredicateOut) => {
    setShowWorkflowModal(false);
    setSelectedPredicateIds([]);
    // Could switch to a different tab or show success message
  };

  const handleWorkflowCancel = () => {
    setShowWorkflowModal(false);
    setSelectedPredicateIds([]);
  };

  return (
    <div className={className}>
      <Card>
        <h2 className="mb-4 text-2xl font-bold text-gray-900 dark:text-white">
          Predicate Mapping Manager
        </h2>
        <p className="mb-6 text-sm text-gray-600 dark:text-gray-400">
          Discover, analyze, and map predicates from external knowledge sources
          to create a unified predicate vocabulary.
        </p>

        <Tabs
          aria-label="Predicate mapping tabs"
          onActiveTabChange={setActiveTab}
        >
          <Tabs.Item active title="External Predicates" icon={HiDatabase}>
            <ExternalPredicatesTab />
          </Tabs.Item>
          <Tabs.Item title="Similarity Search" icon={HiSearch}>
            <SimilaritySearchTab onClusterSelect={handleClusterSelect} />
          </Tabs.Item>
          <Tabs.Item title="Cluster Analysis" icon={HiCollection}>
            <ClusterVisualizationTab onCreateGlobalPredicate={handleClusterSelect} />
          </Tabs.Item>
          <Tabs.Item title="Manual Mapping" icon={HiPlusCircle}>
            <ManualMappingInterface />
          </Tabs.Item>
          <Tabs.Item title="Relevance Selection" icon={HiCheckCircle}>
            <RelevanceSelectionUI />
          </Tabs.Item>
          <Tabs.Item title="Configuration" icon={HiCog}>
            <MappingConfigurationTab />
          </Tabs.Item>
        </Tabs>
      </Card>

      {/* Mapping Creation Workflow Modal */}
      <Modal
        show={showWorkflowModal}
        onClose={handleWorkflowCancel}
        size="3xl"
      >
        <Modal.Header>Create Global Predicate from Cluster</Modal.Header>
        <Modal.Body>
          <MappingCreationWorkflow
            predicateIds={selectedPredicateIds}
            onComplete={handleWorkflowComplete}
            onCancel={handleWorkflowCancel}
          />
        </Modal.Body>
      </Modal>
    </div>
  );
};

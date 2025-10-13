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
import { Card, Tabs } from "flowbite-react";
import { HiDatabase, HiSearch, HiCollection, HiCog } from "react-icons/hi";
import { ExternalPredicatesTab } from "./ExternalPredicatesTab";
import { SimilaritySearchTab } from "./SimilaritySearchTab";
import { ClusterVisualizationTab } from "./ClusterVisualizationTab";
import { MappingConfigurationTab } from "./MappingConfigurationTab";

export interface PredicateMappingManagerProps {
  className?: string;
}

export const PredicateMappingManager: React.FC<
  PredicateMappingManagerProps
> = ({ className }) => {
  const [activeTab, setActiveTab] = useState<number>(0);

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
            <SimilaritySearchTab />
          </Tabs.Item>
          <Tabs.Item title="Cluster Analysis" icon={HiCollection}>
            <ClusterVisualizationTab />
          </Tabs.Item>
          <Tabs.Item title="Configuration" icon={HiCog}>
            <MappingConfigurationTab />
          </Tabs.Item>
        </Tabs>
      </Card>
    </div>
  );
};

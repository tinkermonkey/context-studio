import React from "react";
import {
  Spinner,
  Button,
  Breadcrumb,
  BreadcrumbItem,
  Modal,
  ModalHeader,
  ModalBody,
} from "flowbite-react";
import {
  Calendar,
  Hash,
  Edit3,
  Database,
  Layers,
  Brain,
} from "lucide-react";
import { NodeType } from "@/api/types/structureNodes";
import { useTermHierarchy } from "@/api/hooks/graph/useGraph";
import { useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { LayerForm } from "@/components/forms/layer_form";
import { DomainForm } from "@/components/forms/domain_form";
import { TermForm } from "@/components/forms/term_form";
import {
  CsSidebar,
  CsSidebarTitle,
  CsSidebarSection,
} from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import type { components } from "@/api/client/types";
import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";
import { TreeChartPanel } from "@/components/panels/TreeChartPanel";
import type { StructureNode } from "@/api/types/structureNodes";
import { TreeMenuPanel } from "@/components/panels/TreeMenuPanel";
import { useNlpAnalysisStore } from "@/stores/nlpAnalysisStore";

type NodeOut = components["schemas"]["NodeOut"];

interface StructureNodeDetailsProps {
  node: StructureNode;
}

export const StructureNodeDetails: React.FC<StructureNodeDetailsProps> = ({
  node,
}) => {
  const [isEditOpen, setIsEditOpen] = React.useState(false);
  const { setText, triggerAnalysis } = useNlpAnalysisStore();

  // Handle analyze button click
  const handleAnalyze = React.useCallback(() => {
    setText(node.title);
    triggerAnalysis();
  }, [node.title, setText, triggerAnalysis]);

  // Helper to get icon for a node type
  const getIconForType = (nodeType: string) => {
    switch (nodeType) {
      case NodeType.LAYER:
        return Layers;
      case NodeType.DOMAIN:
        return Database;
      case NodeType.TERM:
        return Hash;
      default:
        return Hash;
    }
  };

  const NodeIcon = getIconForType(node.node_type);

  // Load hierarchy data for all nodes
  const { data: hierarchy, isLoading: hierarchyLoading } = useTermHierarchy(
    node.id,
  );

  // Build lineage from hierarchy for all nodes
  const lineage = React.useMemo(() => {
    if (!hierarchy || hierarchyLoading) {
      return [node];
    }

    const ancestors =
      (hierarchy.ancestors as Array<{
        id: string;
        type: string;
        title: string;
        distance: number;
      }>) || [];

    // Sort ancestors by distance (furthest first)
    const sortedAncestors = [...ancestors].sort((a, b) => b.distance - a.distance);

    // Convert to NodeOut format
    const ancestorNodes: NodeOut[] = sortedAncestors.map((ancestor) => ({
      id: ancestor.id,
      title: ancestor.title,
      node_type: ancestor.type as NodeType,
      parent_node_id: undefined,
      definition: "",
      structural_predicate_id: undefined,
      title_embedding: undefined,
      definition_embedding: undefined,
      created_at: "",
      version: 1,
      last_modified: "",
    }));

    return [...ancestorNodes, node];
  }, [hierarchy, hierarchyLoading, node]);

  // Extract parent nodes from lineage
  const { parentLayer, parentDomain, parentTerm } = React.useMemo(() => {
    const layer = lineage.find((n) => n.node_type === NodeType.LAYER);
    const domain = lineage.find((n) => n.node_type === NodeType.DOMAIN);
    // Parent term is the term that comes immediately before the current node
    const currentIndex = lineage.findIndex((n) => n.id === node.id);
    const parentTerm =
      currentIndex > 0 && lineage[currentIndex - 1].node_type === NodeType.TERM
        ? lineage[currentIndex - 1]
        : undefined;

    return {
      parentLayer: layer,
      parentDomain: domain,
      parentTerm,
    };
  }, [lineage, node.id]);

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Structure Navigation</CsSidebarTitle>
        <CsSidebarSection>
          <TreeMenuPanel viewId="sidebar" />
        </CsSidebarSection>
      </CsSidebar>

      <CsMain>
        {/* Breadcrumb */}
        <div className="mt-2 mb-4">
          <Breadcrumb aria-label="Node hierarchy breadcrumb">
            {hierarchyLoading ? (
              <BreadcrumbItem>
                <Spinner size="sm" />
                <span className="ml-1">Loading hierarchy...</span>
              </BreadcrumbItem>
            ) : (
              (() => {

                // If lineage is short (3 or fewer items), show all
                if (lineage.length <= 4) {
                  return lineage.map((ancestorNode, index) => {
                    const isLast = index === lineage.length - 1;
                    const icon = getIconForType(ancestorNode.node_type);
                    return (
                      <BreadcrumbItem
                        key={ancestorNode.id}
                        href={
                          isLast
                            ? undefined
                            : `/app/structure_nodes/${ancestorNode.id}`
                        }
                        icon={icon}
                      >
                        {ancestorNode.title}
                      </BreadcrumbItem>
                    );
                  });
                }

                // For longer lineages, show first ... last
                const breadcrumbItems = [];
                const first = lineage[0];
                const last = lineage[lineage.length - 1];

                breadcrumbItems.push(
                  <BreadcrumbItem
                    key={first.id}
                    href={`/app/structure_nodes/${first.id}`}
                    icon={getIconForType(first.node_type)}
                  >
                    {first.title}
                  </BreadcrumbItem>,
                );

                breadcrumbItems.push(
                  <BreadcrumbItem key="ellipsis">...</BreadcrumbItem>,
                );

                breadcrumbItems.push(
                  <BreadcrumbItem
                    key={last.id}
                    icon={getIconForType(last.node_type)}
                  >
                    {last.title}
                  </BreadcrumbItem>,
                );

                return breadcrumbItems;
              })()
            )}
          </Breadcrumb>
        </div>

        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <CsMainTitle icon={NodeIcon}>{node.title}</CsMainTitle>
            <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center gap-1">
                <Hash className="h-4 w-4" />
                <span className="font-mono">{node.id}</span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                <span>Version {node.version}</span>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button color="gray" size="sm" onClick={handleAnalyze}>
              <Brain className="mr-2 h-4 w-4" />
              Analyze
            </Button>
            <Button color="gray" size="sm" onClick={() => setIsEditOpen(true)}>
              <Edit3 className="mr-2 h-4 w-4" />
              Edit
            </Button>
          </div>
        </div>

        <div className="space-y-6">
          {/* NLP Analysis */}
          <NlpAnalysisPanel
            text={node.title}
            textTitle={node.node_type === NodeType.TERM ? "Term" : "Title"}
            domainContext={
              parentDomain
                ? {
                    title: parentDomain.title,
                    definition: parentDomain.definition || "",
                  }
                : null
            }
            parentTermContext={
              parentTerm
                ? {
                    title: parentTerm.title,
                    definition: parentTerm.definition || "",
                    relationshipPredicate: "child_of",
                  }
                : null
            }
            currentDefinition={node.definition}
            layerId={
              node.node_type === NodeType.LAYER
                ? node.id
                : parentLayer?.id
            }
            domainId={
              node.node_type === NodeType.DOMAIN
                ? node.id
                : parentDomain?.id
            }
            termId={node.node_type === NodeType.TERM ? node.id : undefined}
          />

          {/* Definition */}
          {node.definition && (
            <div className="pt-4">
              <h2 className="mb-3 text-xl font-semibold">Definition</h2>
              <p className="leading-relaxed text-gray-700 dark:text-gray-300">
                {node.definition}
              </p>
            </div>
          )}

          {/* Term Hierarchy */}
          <div className="pt-4">
            <h2 className="text-xl font-semibold">Hierarchy</h2>
            <TreeChartPanel
              layerId={node.node_type === NodeType.LAYER ? node.id : undefined}
              domainId={
                node.node_type === NodeType.DOMAIN ? node.id : undefined
              }
              termId={node.node_type === NodeType.TERM ? node.id : undefined}
            />
          </div>
        </div>
      </CsMain>

      <EditModal
        node={node}
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
      />
    </>
  );
};

// Edit Modal
const EditModal: React.FC<{
  node: StructureNode;
  isOpen: boolean;
  onClose: () => void;
}> = ({ node, isOpen, onClose }) => {
  const queryClient = useQueryClient();

  const handleSuccess = () => {
    onClose();

    try {
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES, node.id],
      });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.STRUCTURE_NODES] });
    } catch (e) {
      console.warn("Failed to invalidate node queries", e);
    }
  };

  const getModalTitle = () => {
    switch (node.node_type) {
      case NodeType.LAYER:
        return "Edit Layer";
      case NodeType.DOMAIN:
        return "Edit Domain";
      case NodeType.TERM:
        return "Edit Term";
      default:
        return "Edit Node";
    }
  };

  const getForm = () => {
    switch (node.node_type) {
      case NodeType.LAYER:
        return <LayerForm layer={node} onSuccess={handleSuccess} />;
      case NodeType.DOMAIN:
        return <DomainForm domain={node} onSuccess={handleSuccess} />;
      case NodeType.TERM:
        return <TermForm term={node} onSuccess={handleSuccess} />;
      default:
        return null;
    }
  };

  return (
    <Modal show={isOpen} onClose={onClose}>
      <ModalHeader className="border-b-0">{getModalTitle()}</ModalHeader>
      <ModalBody>{getForm()}</ModalBody>
    </Modal>
  );
};

import React from "react";
import {
  Spinner,
  Button,
  Breadcrumb,
  BreadcrumbItem,
  Modal,
  ModalHeader,
  ModalBody,
  Textarea,
} from "flowbite-react";
import {
  Calendar,
  Hash,
  Edit3,
  Database,
  Layers,
  Brain,
  Check,
  X,
  Plus,
  Move,
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
import { CsMain, CsMainTitle, CsMainHeader } from "@/components/layout/cs_main";
import type { components } from "@/api/client/types";
import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";
import { TreeChartPanel } from "@/components/panels/TreeChartPanel";
import type { StructureNode } from "@/api/types/structureNodes";
import { TreeMenuPanel } from "@/components/panels/TreeMenuPanel";
import { useNlpAnalysisStore } from "@/stores/nlpAnalysisStore";
import { useUpdateStructureNode } from "@/api/hooks/structure_nodes/useStructureNodeMutations";
import { toast } from "@/utils/toast";
import { ReferenceNodePanel } from "@/components/reference_nodes";
import { DomainMoveForm } from "@/components/forms/domain_move_form";
import { TermMoveForm } from "@/components/forms/term_move_form";

type NodeOut = components["schemas"]["NodeOut"];

interface StructureNodeDetailsProps {
  node: StructureNode;
}

export const StructureNodeDetails: React.FC<StructureNodeDetailsProps> = ({
  node,
}) => {
  const [isEditOpen, setIsEditOpen] = React.useState(false);
  const [isAddChildOpen, setIsAddChildOpen] = React.useState(false);
  const [isMoveOpen, setIsMoveOpen] = React.useState(false);
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
          <TreeMenuPanel
            key="structure-navigation-tree"
            viewId="sidebar"
            highlightedTermId={node.id}
          />
        </CsSidebarSection>
      </CsSidebar>

      <CsMain>
        <CsMainHeader>
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
              <CsMainTitle icon={NodeIcon} data-testid="node-detail-title">{node.title}</CsMainTitle>
              <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                <div className="flex items-center gap-1">
                  <Hash className="h-4 w-4" />
                  <span className="font-mono" data-testid="node-detail-id">{node.id}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  <span data-testid="node-detail-type">{node.node_type} - Version {node.version}</span>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <Button color="gray" size="sm" onClick={handleAnalyze}>
                <Brain className="mr-2 h-4 w-4" />
                Analyze
              </Button>
              <Button color="gray" size="sm" onClick={() => setIsAddChildOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Add Child
              </Button>
              {node.node_type !== NodeType.LAYER && (
                <Button color="gray" size="sm" onClick={() => setIsMoveOpen(true)}>
                  <Move className="mr-2 h-4 w-4" />
                  Move
                </Button>
              )}
              <Button color="gray" size="sm" onClick={() => setIsEditOpen(true)}>
                <Edit3 className="mr-2 h-4 w-4" />
                Edit
              </Button>
            </div>
          </div>
        </CsMainHeader>

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
            nodeId={node.id}
          />

          {/* Definition */}
          <div className="pt-4" data-testid="node-detail-definition-section">
            <h2 className="mb-3 text-xl font-semibold">Definition</h2>
            <div data-testid="node-detail-definition">
              <EditableDefinition node={node} />
            </div>
          </div>

          {/* Reference Nodes */}
          <div className="pt-4">
            <ReferenceNodePanel nodeId={node.id} nodeTitle={node.title} />
          </div>

          {/* Term Hierarchy */}
          <div className="pt-4" data-testid="node-children-section">
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
      <AddChildModal
        node={node}
        isOpen={isAddChildOpen}
        onClose={() => setIsAddChildOpen(false)}
      />
      <MoveModal
        node={node}
        isOpen={isMoveOpen}
        onClose={() => setIsMoveOpen(false)}
      />
    </>
  );
};

// Editable Definition Component
const EditableDefinition: React.FC<{ node: StructureNode }> = ({ node }) => {
  const [isEditing, setIsEditing] = React.useState(false);
  const [value, setValue] = React.useState(node.definition || "");
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const updateMutation = useUpdateStructureNode();

  // Auto-resize textarea to fit content
  const autoResizeTextarea = React.useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = 'auto';
      // Set height to scrollHeight to fit content
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, []);

  // Update value when node changes
  React.useEffect(() => {
    setValue(node.definition || "");
  }, [node.definition]);

  // Focus textarea and resize when entering edit mode
  React.useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      // Move cursor to end
      const length = textareaRef.current.value.length;
      textareaRef.current.setSelectionRange(length, length);
      // Initial resize
      autoResizeTextarea();
    }
  }, [isEditing, autoResizeTextarea]);

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({
        id: node.id,
        data: { definition: value },
      });
      setIsEditing(false);
      toast.success("Definition updated successfully");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to update definition",
      );
    }
  };

  const handleCancel = () => {
    setValue(node.definition || "");
    setIsEditing(false);
  };

  const handleDoubleClick = () => {
    setIsEditing(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      handleCancel();
    }
  };

  if (isEditing) {
    return (
      <div>
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            autoResizeTextarea();
          }}
          onKeyDown={handleKeyDown}
          rows={1}
          className="leading-relaxed text-gray-700 dark:text-gray-300 text-base font-normal p-2 resize-none overflow-hidden"
          style={{ fontFamily: 'inherit' }}
          disabled={updateMutation.isPending}
        />
        <div className="mt-2 flex gap-2">
          <Button
            size="sm"
            onClick={handleSave}
            disabled={updateMutation.isPending}
          >
            <Check className="mr-1 h-4 w-4" />
            Save
          </Button>
          <Button
            size="sm"
            color="gray"
            onClick={handleCancel}
            disabled={updateMutation.isPending}
          >
            <X className="mr-1 h-4 w-4" />
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  const [isHovered, setIsHovered] = React.useState(false);

  return (
    <div
      onDoubleClick={handleDoubleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="cursor-text leading-relaxed text-gray-700 dark:text-gray-300 text-base font-normal min-h-[4rem] p-2 -m-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
      title="Double-click to edit"
    >
      {node.definition || (
        <span className="italic text-gray-400 dark:text-gray-500">
          No definition provided. Double-click to add one.
        </span>
      )}
      <div className={`text-xs text-gray-400 dark:text-gray-500 mt-2 italic transition-opacity duration-200 ${isHovered ? 'opacity-100' : 'opacity-0'}`}>
        Double-click to edit
      </div>
    </div>
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

// Add Child Modal
const AddChildModal: React.FC<{
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
        return "Add Domain";
      case NodeType.DOMAIN:
        return "Add Term";
      case NodeType.TERM:
        return "Add Child Term";
      default:
        return "Add Child Node";
    }
  };

  const getForm = () => {
    switch (node.node_type) {
      case NodeType.LAYER:
        return (
          <DomainForm
            parentLayerId={node.id}
            parentLayer={node}
            mode="child"
            onSuccess={handleSuccess}
          />
        );
      case NodeType.DOMAIN:
        return (
          <TermForm
            parentDomainId={node.id}
            parentDomain={node}
            mode="child"
            onSuccess={handleSuccess}
          />
        );
      case NodeType.TERM:
        return (
          <TermForm
            parentTermId={node.id}
            parentTerm={node}
            mode="child"
            onSuccess={handleSuccess}
          />
        );
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

// Move Modal
const MoveModal: React.FC<{
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
      case NodeType.DOMAIN:
        return "Move Domain";
      case NodeType.TERM:
        return "Move Term";
      default:
        return "Move Node";
    }
  };

  const getForm = () => {
    switch (node.node_type) {
      case NodeType.DOMAIN:
        return (
          <DomainMoveForm
            selectedNodes={[node]}
            onSuccess={handleSuccess}
            onCancel={onClose}
          />
        );
      case NodeType.TERM:
        return (
          <TermMoveForm
            selectedNodes={[node]}
            onSuccess={handleSuccess}
            onCancel={onClose}
          />
        );
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

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
  Brain,
  Calendar,
  Check,
  Database,
  Edit3,
  Hash,
  Layers,
  Move,
  Plus,
  X,
} from "lucide-react";
import { NodeType } from "@/api/types/changeEvents";
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
import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";
import { TreeChartPanel } from "@/components/panels/TreeChartPanel";
import type { OntologyClass } from "@/api/types/ontology";
import { TreeMenuPanel } from "@/components/panels/TreeMenuPanel";
import { useNlpAnalysisStore } from "@/stores/nlpAnalysisStore";
import { useUpdateTaxonomy } from "@/api/hooks/taxonomies/useTaxonomies";
import { useUpdateConceptScheme } from "@/api/hooks/conceptSchemes/useConceptSchemes";
import { useUpdateOntologyClass } from "@/api/hooks/ontologyClasses/useOntologyClasses";
import { toast } from "@/utils/toast";
import { ReferenceNodePanel } from "@/components/reference_nodes";
import { NodeLinkPanel } from "@/components/node_links";
import { DomainMoveForm } from "@/components/forms/domain_move_form";
import { TermMoveForm } from "@/components/forms/term_move_form";
import { AttributePanel } from "@/components/structure_nodes/AttributePanel";
import type { NodeOut } from "@/api/services/missingTypes";

interface OntologyClassDetailsProps {
  node: OntologyClass;
}

export const OntologyClassDetails: React.FC<OntologyClassDetailsProps> = ({
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
      case "taxonomy":
      case "layer":
        return Layers;
      case "scheme":
      case "domain":
        return Database;
      case "class":
      case "term":
        return Hash;
      default:
        return Hash;
    }
  };

  const NodeIcon = getIconForType(node.node_type || "");

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
    const sortedAncestors = [...ancestors].sort(
      (a, b) => b.distance - a.distance,
    );

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
    const layer = lineage.find((n) => n.node_type === "taxonomy");
    const domain = lineage.find((n) => n.node_type === "scheme");
    // Parent term is the term that comes immediately before the current node
    const currentIndex = lineage.findIndex((n) => n.id === node.id);
    const parentTerm =
      currentIndex > 0 && lineage[currentIndex - 1].node_type === "class"
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
                      const icon = getIconForType(
                        ancestorNode.node_type as string,
                      );
                      return (
                        <BreadcrumbItem
                          key={ancestorNode.id}
                          href={
                            isLast
                              ? undefined
                              : `/app/ontologyClass/${ancestorNode.id}`
                          }
                          icon={icon}
                        >
                          {ancestorNode.title as string}
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
                      href={`/app/ontologyClass/${first.id}`}
                      icon={getIconForType(first.node_type as string)}
                    >
                      {first.title as string}
                    </BreadcrumbItem>,
                  );

                  breadcrumbItems.push(
                    <BreadcrumbItem key="ellipsis">...</BreadcrumbItem>,
                  );

                  breadcrumbItems.push(
                    <BreadcrumbItem
                      key={last.id}
                      icon={getIconForType(last.node_type as string)}
                    >
                      {last.title as string}
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
              <CsMainTitle icon={NodeIcon} data-testid="node-detail-title">
                {node.title}
              </CsMainTitle>
              <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                <div className="flex items-center gap-1">
                  <Hash className="h-4 w-4" />
                  <span className="font-mono" data-testid="node-detail-id">
                    {node.id}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  <span data-testid="node-detail-type">
                    {node.node_type} - Version {node.version}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <Button color="gray" size="sm" onClick={handleAnalyze}>
                <Brain className="mr-2 h-4 w-4" />
                Analyze
              </Button>
              <Button
                color="gray"
                size="sm"
                onClick={() => setIsAddChildOpen(true)}
              >
                <Plus className="mr-2 h-4 w-4" />
                Add Child
              </Button>
              {node.node_type !== "taxonomy" && (
                <Button
                  color="gray"
                  size="sm"
                  onClick={() => setIsMoveOpen(true)}
                >
                  <Move className="mr-2 h-4 w-4" />
                  Move
                </Button>
              )}
              <Button
                color="gray"
                size="sm"
                onClick={() => setIsEditOpen(true)}
              >
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
            textTitle={node.node_type === "class" ? "Term" : "Title"}
            domainContext={
              parentDomain
                ? {
                    title: parentDomain.title as string,
                    definition: (parentDomain.definition || "") as string,
                  }
                : null
            }
            parentTermContext={
              parentTerm
                ? {
                    title: parentTerm.title as string,
                    definition: (parentTerm.definition || "") as string,
                    relationshipPredicate: "child_of",
                  }
                : null
            }
            currentDefinition={node.definition}
            layerId={node.node_type === "taxonomy" ? node.id : parentLayer?.id}
            domainId={node.node_type === "scheme" ? node.id : parentDomain?.id}
            termId={node.node_type === "class" ? node.id : undefined}
            nodeId={node.id}
          />

          {/* Definition */}
          <div className="pt-4" data-testid="node-detail-definition-section">
            <h2 className="mb-3 text-xl font-semibold">Definition</h2>
            <div data-testid="node-detail-definition">
              <EditableDefinition node={node} />
            </div>
          </div>

          {/* Attributes */}
          <div className="pt-4" data-testid="node-attributes-section">
            <AttributePanel nodeId={node.id} />
          </div>

          {/* Reference Nodes */}
          <div className="pt-4">
            <ReferenceNodePanel nodeId={node.id} nodeTitle={node.title} />
          </div>

          {/* Node Links */}
          <div className="pt-4">
            <NodeLinkPanel nodeId={node.id} node={node} />
          </div>

          {/* Term Hierarchy */}
          <div className="pt-4" data-testid="node-children-section">
            <h2 className="text-xl font-semibold">Hierarchy</h2>
            <TreeChartPanel
              layerId={node.node_type === "taxonomy" ? node.id : undefined}
              domainId={node.node_type === "scheme" ? node.id : undefined}
              termId={node.node_type === "class" ? node.id : undefined}
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
const EditableDefinition: React.FC<{ node: OntologyClass }> = ({ node }) => {
  const [isEditing, setIsEditing] = React.useState(false);
  const [value, setValue] = React.useState(node.definition || "");
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  // Get the appropriate mutation based on node type
  const taxonomyMutation = useUpdateTaxonomy();
  const conceptSchemeMutation = useUpdateConceptScheme();
  const ontologyClassMutation = useUpdateOntologyClass();

  // Select the appropriate mutation based on node type
  const getUpdateMutation = () => {
    switch (node.node_type) {
      case "taxonomy":
      case "layer":
        return taxonomyMutation;
      case "scheme":
      case "domain":
        return conceptSchemeMutation;
      case "class":
      case "term":
        return ontologyClassMutation;
      default:
        return taxonomyMutation;
    }
  };

  const updateMutation = getUpdateMutation();

  // Auto-resize textarea to fit content
  const autoResizeTextarea = React.useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = "auto";
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
          className="resize-none overflow-hidden p-2 text-base leading-relaxed font-normal text-gray-700 dark:text-gray-300"
          style={{ fontFamily: "inherit" }}
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
      className="-m-2 min-h-[4rem] cursor-text rounded p-2 text-base leading-relaxed font-normal text-gray-700 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
      title="Double-click to edit"
    >
      {node.definition || (
        <span className="text-gray-400 italic dark:text-gray-500">
          No definition provided. Double-click to add one.
        </span>
      )}
      <div
        className={`mt-2 text-xs text-gray-400 italic transition-opacity duration-200 dark:text-gray-500 ${isHovered ? "opacity-100" : "opacity-0"}`}
      >
        Double-click to edit
      </div>
    </div>
  );
};

// Edit Modal
const EditModal: React.FC<{
  node: OntologyClass;
  isOpen: boolean;
  onClose: () => void;
}> = ({ node, isOpen, onClose }) => {
  const queryClient = useQueryClient();

  const handleSuccess = () => {
    onClose();

    try {
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES, node.id],
      });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES] });
    } catch (e) {
      console.warn("Failed to invalidate node queries", e);
    }
  };

  const getModalTitle = () => {
    switch (node.node_type) {
      case "taxonomy":
      case "layer":
        return "Edit Layer";
      case "scheme":
      case "domain":
        return "Edit Domain";
      case "class":
      case "term":
        return "Edit Term";
      default:
        return "Edit Node";
    }
  };

  const getForm = () => {
    switch (node.node_type) {
      case "taxonomy":
      case "layer":
        return <LayerForm layer={node} onSuccess={handleSuccess} />;
      case "scheme":
      case "domain":
        return <DomainForm domain={node} onSuccess={handleSuccess} />;
      case "class":
      case "term":
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
  node: OntologyClass;
  isOpen: boolean;
  onClose: () => void;
}> = ({ node, isOpen, onClose }) => {
  const queryClient = useQueryClient();

  const handleSuccess = () => {
    onClose();

    try {
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES, node.id],
      });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES] });
    } catch (e) {
      console.warn("Failed to invalidate node queries", e);
    }
  };

  const getModalTitle = () => {
    switch (node.node_type) {
      case "taxonomy":
      case "layer":
        return "Add Domain";
      case "scheme":
      case "domain":
        return "Add Term";
      case "class":
      case "term":
        return "Add Child Term";
      default:
        return "Add Child Node";
    }
  };

  const getForm = () => {
    switch (node.node_type) {
      case "taxonomy":
      case "layer":
        return (
          <DomainForm
            parentLayerId={node.id}
            parentLayer={node}
            mode="child"
            onSuccess={handleSuccess}
          />
        );
      case "scheme":
      case "domain":
        return (
          <TermForm
            parentDomainId={node.id}
            parentDomain={node}
            mode="child"
            onSuccess={handleSuccess}
          />
        );
      case "class":
      case "term":
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
  node: OntologyClass;
  isOpen: boolean;
  onClose: () => void;
}> = ({ node, isOpen, onClose }) => {
  const queryClient = useQueryClient();

  const handleSuccess = () => {
    onClose();

    try {
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES, node.id],
      });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES] });
    } catch (e) {
      console.warn("Failed to invalidate node queries", e);
    }
  };

  const getModalTitle = () => {
    switch (node.node_type) {
      case "scheme":
      case "domain":
        return "Move Domain";
      case "class":
      case "term":
        return "Move Term";
      default:
        return "Move Node";
    }
  };

  const getForm = () => {
    switch (node.node_type) {
      case "scheme":
      case "domain":
        return (
          <DomainMoveForm
            selectedNodes={[node]}
            onSuccess={handleSuccess}
            onCancel={onClose}
          />
        );
      case "class":
      case "term":
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

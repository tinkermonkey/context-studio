import React from "react";
import {
  Card,
  Spinner,
  Button,
  Badge,
  Modal,
  ModalHeader,
  ModalBody,
} from "flowbite-react";
import {
  Calendar,
  Edit3,
  Database,
  FileText,
  CircleArrowRight,
  Layers,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";
import {
  useDomainNodes,
  useTermNodes,
  useStructureNode,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import { TermRenderer } from "@/components/node_renderers/term_renderer";
import { CreateChildButton } from "@/components/misc/create_child_button";
import { LayerForm } from "@/components/forms/layer_form";
import { useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import {
  CsSidebar,
  CsSidebarTitle,
  CsSidebarSection,
  CsSidebarSectionTitle,
} from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import type { StructureNode } from "@/api/types/structureNodes";
import { TreeMenuPanel } from "@/components/panels/TreeMenuPanel";

interface LayerDetailsProps {
  layer: StructureNode;
}

export const LayerDetails: React.FC<LayerDetailsProps> = ({ layer }) => {
  const queryClient = useQueryClient();
  const [isEditOpen, setIsEditOpen] = React.useState(false);
  const { data: terms, isLoading: termsLoading } = useTermNodes();

  const { data: domains, isLoading: domainsLoading } = useDomainNodes(layer.id);

  // Group terms by domain for better organization
  const termsByDomain = React.useMemo(() => {
    if (!terms) return {};

    const grouped: Record<string, StructureNode[]> = {};

    terms.forEach((term: StructureNode) => {
      // Find the term's domain by checking its parent hierarchy
      const domainParent =
        domains?.find((d) => d.id === term.parent_node_id) ||
        domains?.find((d) =>
          terms.some(
            (t) => t.parent_node_id === d.id && t.id === term.parent_node_id,
          ),
        );
      const domainId = domainParent?.id || "unknown";

      if (!grouped[domainId]) {
        grouped[domainId] = [];
      }
      grouped[domainId].push(term);
    });

    return grouped;
  }, [terms]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>Context</CsSidebarTitle>

        {/* Statistics */}
        <CsSidebarSection>
          <CsSidebarSectionTitle icon={FileText}>
            Statistics
          </CsSidebarSectionTitle>
          <div className="mx-2 inline-block space-y-2">
            <div className="flex justify-between">
              <span className="text-sm">Total Terms:</span>
              <span className="pl-2 font-semibold">{terms?.length || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">Domains:</span>
              <span className="pl-2 font-semibold">{domains?.length || 0}</span>
            </div>
          </div>
        </CsSidebarSection>

        <CsSidebarTitle>Metadata</CsSidebarTitle>
        <CsSidebarSection>
          <div className="mx-2 space-y-2">
            <div>
              <span className="font-semibold">Created:</span>
              <div className="text-gray-600 dark:text-gray-400">
                {formatDate(layer.created_at)}
              </div>
            </div>
            <div>
              <span className="font-semibold">Version:</span>
              <div className="text-gray-600 dark:text-gray-400">
                {layer.version || 1}
              </div>
            </div>
          </div>
        </CsSidebarSection>
      </CsSidebar>

      <CsMain>
        <div className="mb-6 flex items-center justify-between">
          <div>
            <CsMainTitle icon={Layers}>{layer.title}</CsMainTitle>
            <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center gap-1">
                <span className="font-mono">{layer.id}</span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                <span>Version {layer.version || 1}</span>
              </div>
            </div>
          </div>
          <Button color="gray" size="sm" onClick={() => setIsEditOpen(true)}>
            <Edit3 className="mr-2 h-4 w-4" />
            Edit
          </Button>
        </div>

        <div className="space-y-6">
          {/* NLP title analysis for the layer */}
          <NlpAnalysisPanel
            text={layer.title}
            textTitle={"Title"}
            currentDefinition={layer.definition}
            layerId={layer.id}
          />

          {/* Definition */}
          {layer.definition && (
            <div className="pt-4">
              <h2 className="mb-3 text-xl font-semibold">Definition</h2>
              <p className="leading-relaxed text-gray-700 dark:text-gray-300">
                {layer.definition}
              </p>
            </div>
          )}

          {/* Domains in this Layer */}
          <div className="pt-4">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Domains in this Layer</h2>
              <div className="flex items-center gap-2">
                <Badge color="info" size="sm">
                  {domains?.length || 0} domain
                  {domains && domains.length !== 1 ? "s" : ""}
                </Badge>
                <CreateChildButton
                  parentType="layer"
                  parentId={layer.id}
                  parentObject={layer}
                  childType="domain"
                />
              </div>
            </div>

            {domainsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Spinner size="md" />
                <span className="ml-2">Loading domains...</span>
              </div>
            ) : !domains || domains.length === 0 ? (
              <p className="text-gray-500 italic dark:text-gray-400">
                No domains found in this layer.
              </p>
            ) : (
              <div className="space-y-4">
                {domains.map((domain) => (
                  <DomainTermsSection
                    key={domain.id}
                    domainId={domain.id}
                    terms={termsByDomain[domain.id] || []}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </CsMain>
      <LayerEditModal
        layer={layer}
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
      />
    </>
  );
};

// Edit Modal for Layer
const LayerEditModal: React.FC<{
  layer: StructureNode;
  isOpen: boolean;
  onClose: () => void;
}> = ({ layer, isOpen, onClose }) => {
  const queryClient = useQueryClient();

  const handleSuccess = (updated: any) => {
    // Close modal
    onClose();

    // Invalidate layer queries so details refresh
    try {
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.LAYERS, layer.id],
      });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.LAYERS] });
    } catch (e) {
      // best-effort
      console.warn("Failed to invalidate layer queries", e);
    }
  };

  return (
    <Modal show={isOpen} onClose={onClose} size="lg">
      <ModalHeader className="border-b-0">Edit Layer</ModalHeader>
      <ModalBody>
        <LayerForm layer={layer} onSuccess={handleSuccess} />
      </ModalBody>
    </Modal>
  );
};

// Helper component to display terms grouped by domain
interface DomainTermsSectionProps {
  domainId: string;
  terms: StructureNode[];
}

const DomainTermsSection: React.FC<DomainTermsSectionProps> = ({
  domainId,
  terms,
}) => {
  const { data: domain, isLoading: domainLoading } = useStructureNode(domainId);

  return (
    <div className="rounded-lg border p-4 dark:border-gray-600">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-medium">
          <Database className="h-4 w-4" />
          {domainLoading ? (
            <Spinner size="sm" />
          ) : domain ? (
            <div className="flex items-center gap-2">
              <span>{domain.title}</span>
              <Link
                to="/app/nodes/domain/$domainId"
                params={{ domainId: domain.id }}
                className="text-gray-400 transition-colors hover:text-blue-600 dark:hover:text-blue-400"
              >
                <CircleArrowRight className="h-4 w-4" />
              </Link>
            </div>
          ) : (
            <span className="text-gray-500 italic">Unknown Domain</span>
          )}
        </h3>
        <div className="flex items-center gap-2">
          <Badge color="gray" size="sm">
            {terms.length} term{terms.length !== 1 ? "s" : ""}
          </Badge>
          {domain && (
            <CreateChildButton
              parentType="domain"
              parentId={domainId}
              parentObject={domain}
              childType="term"
            />
          )}
        </div>
      </div>

      {domain?.definition && (
        <p className="mb-3 text-sm text-gray-600 dark:text-gray-400">
          {domain.definition}
        </p>
      )}

      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        {terms.map((term) => (
          <div
            key={term.id}
            className="flex items-center rounded-lg bg-gray-50 p-3 dark:bg-gray-700"
          >
            <TermRenderer term_id={term.id} />
            <Link
              to="/app/nodes/term/$termId"
              params={{ termId: term.id }}
              className="ml-2 text-gray-400 transition-colors hover:text-blue-600 dark:hover:text-blue-400"
            >
              <CircleArrowRight className="h-4 w-4" />
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
};

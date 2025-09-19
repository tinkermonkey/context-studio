import React from "react";
import {
  Card,
  Spinner,
  Button,
  Breadcrumb,
  BreadcrumbItem,
  Badge,
  Modal,
  ModalHeader,
  ModalBody,
} from "flowbite-react";
import {
  Calendar,
  Hash,
  Link,
  Edit3,
  Database,
  Layers,
  CircleArrowRight,
} from "lucide-react";
import { Link as RouterLink } from "@tanstack/react-router";
import {
  useStructureNode,
  useTermNodes,
} from "@/api/hooks/structure_nodes/useStructureNodes";
import { useNodeLinks } from "@/api/hooks/node_links/useNodeLinks";
import { NodeType } from "@/api/types/structureNodes";
import { useTermHierarchy } from "@/api/hooks/graph/useGraph";
import { TermRenderer } from "@/components/node_renderers/term_renderer";
import { useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { TermForm } from "@/components/forms/term_form";
import { RelationshipTermsDisplay } from "@/components/node_renderers/relationship_terms_renderer";
import { CreateChildButton } from "@/components/misc/create_child_button";
import {
  CsSidebar,
  CsSidebarTitle,
  CsSidebarSection,
  CsSidebarSectionTitle,
} from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import type { components } from "@/api/client/types";
import { NlpAnalysisPanel } from "@/components/nlp/NlpAnalysisPanel";
import { TreeChartPanel } from "@/components/panels/TreeChartPanel";

import type { StructureNode } from "@/api/types/structureNodes";
type NodeOut = components["schemas"]["NodeOut"];
type NodeLinkOut = components["schemas"]["NodeLinkOut"];

interface TermPageProps {
  term: StructureNode;
}

export const TermDetails: React.FC<TermPageProps> = ({ term }) => {
  const queryClient = useQueryClient();
  const [isEditOpen, setIsEditOpen] = React.useState(false);
  // For now, assume direct parent is domain (simplified approach)
  // TODO: Implement full hierarchy traversal when needed
  const { data: parentNode } = useStructureNode(term.parent_node_id ?? "");

  // Try to get domain - either the parent is a domain, or we need to traverse further
  const isDomainParent = parentNode?.node_type === NodeType.DOMAIN;
  const { data: domain, isLoading: domainLoading } = useStructureNode(
    isDomainParent ? (parentNode?.id ?? "") : "",
  );

  // Get layer from domain if we have it
  const { data: layer, isLoading: layerLoading } = useStructureNode(
    domain?.parent_node_id ?? "",
  );
  // Use parentNode for both domain and term parents
  const parentTerm = !isDomainParent ? (parentNode as any) : null;
  const parentTermLoading = false; // Already loaded via parentNode
  const { data: relationships, isLoading: relationshipsLoading } = useNodeLinks(
    { source_node_id: term.id },
  );
  const { data: termHierarchy, isLoading: hierarchyLoading } = useTermHierarchy(
    term.id,
  );
  const { data: childTerms, isLoading: childTermsLoading } = useTermNodes(
    term.id,
  );

  // Group relationships by predicate and direction
  const relationshipsByPredicate = React.useMemo(() => {
    if (!relationships) return {};

    const grouped: Record<
      string,
      { asSource: NodeLinkOut[]; asTarget: NodeLinkOut[] }
    > = {};

    relationships.forEach((rel: any) => {
      if (!grouped[rel.predicate]) {
        grouped[rel.predicate] = { asSource: [], asTarget: [] };
      }

      if (rel.source_node_id === term.id) {
        grouped[rel.predicate].asSource.push(rel);
      } else {
        grouped[rel.predicate].asTarget.push(rel);
      }
    });

    return grouped;
  }, [relationships, term.id]);

  // Build term lineage for breadcrumb using hierarchy data
  const termLineage = React.useMemo(() => {
    if (!termHierarchy || hierarchyLoading) {
      // Fallback to simple parent-child if hierarchy is not available
      const lineage: NodeOut[] = [];
      if (parentTerm) {
        lineage.push(parentTerm);
      }
      lineage.push(term);
      return lineage;
    }

    // Use the hierarchy data to build complete lineage
    const ancestors =
      (termHierarchy.ancestors as Array<{
        id: string;
        type: string;
        title: string;
        distance: number;
      }>) || [];

    // Filter and sort term ancestors only
    const termAncestors = ancestors
      .filter((ancestor) => ancestor.type === "term")
      .sort((a, b) => b.distance - a.distance); // Sort by distance descending (farthest first)

    // Create NodeOut-like objects for ancestors
    const ancestorTerms: NodeOut[] = termAncestors.map((ancestor) => ({
      id: ancestor.id,
      title: ancestor.title,
      node_type: NodeType.TERM,
      parent_node_id: undefined, // Not needed for breadcrumb
      definition: "", // Not available in hierarchy data
      structural_predicate_id: undefined,
      title_embedding: undefined,
      definition_embedding: undefined,
      created_at: "",
      version: 1,
      last_modified: "",
    }));

    // Return the complete lineage: ancestors + current term
    return [...ancestorTerms, term];
  }, [termHierarchy, hierarchyLoading, parentTerm, term]);

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

        {/* Layer Information */}
        <CsSidebarSection>
          <CsSidebarSectionTitle icon={Layers}>Layer</CsSidebarSectionTitle>
          {layerLoading ? (
            <Spinner size="sm" />
          ) : layer ? (
            <div className="mx-2">
              <div className="flex items-center">
                <div className="font-semibold">{layer.title}</div>
                <RouterLink
                  to="/app/nodes/layer/$layerId"
                  params={{ layerId: layer.id }}
                  className="hover:text-primary-600 dark:hover:text-primary-300 ml-2 text-gray-400 transition-colors"
                >
                  <CircleArrowRight className="h-4 w-4" />
                </RouterLink>
              </div>
              {layer.definition && (
                <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  {layer.definition}
                </div>
              )}
            </div>
          ) : (
            <span className="text-gray-500 italic">Unknown layer</span>
          )}
        </CsSidebarSection>

        {/* Domain Information */}
        <CsSidebarSection>
          <CsSidebarSectionTitle icon={Database}>Domain</CsSidebarSectionTitle>
          {domainLoading ? (
            <Spinner size="sm" />
          ) : domain ? (
            <div className="mx-2">
              <div className="flex items-center">
                <div className="font-semibold">{domain.title}</div>
                <RouterLink
                  to="/app/nodes/domain/$domainId"
                  params={{ domainId: domain.id }}
                  className="hover:text-primary-600 dark:hover:text-primary-300 ml-2 text-gray-400 transition-colors"
                >
                  <CircleArrowRight className="h-4 w-4" />
                </RouterLink>
              </div>
              <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                {domain.definition}
              </div>
            </div>
          ) : (
            <span className="text-gray-500 italic">Unknown domain</span>
          )}
        </CsSidebarSection>

        {/* Parent Term */}
        {term.parent_node_id && (
          <CsSidebarSection>
            <CsSidebarSectionTitle icon={Hash}>
              Parent Term
            </CsSidebarSectionTitle>

            {parentTermLoading ? (
              <Spinner size="sm" />
            ) : parentTerm ? (
              <div className="mx-2">
                <div className="flex items-center font-semibold">
                  <TermRenderer term_id={parentTerm.id} />
                  <RouterLink
                    to="/app/nodes/term/$termId"
                    params={{ termId: parentTerm.id }}
                    className="hover:text-primary-600 dark:hover:text-primary-300 ml-2 text-gray-400 transition-colors"
                  >
                    <CircleArrowRight className="h-4 w-4" />
                  </RouterLink>
                </div>
                <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  {parentTerm.definition}
                </div>
              </div>
            ) : (
              <span className="text-gray-500 italic">Unknown parent term</span>
            )}
          </CsSidebarSection>
        )}

        <CsSidebarTitle>Metadata</CsSidebarTitle>
        <CsSidebarSection>
          <div className="mx-2 space-y-2">
            <div>
              <span className="font-semibold">Created:</span>
              <div className="text-gray-600 dark:text-gray-400">
                {formatDate(term.created_at)}
              </div>
            </div>
            <div>
              <span className="font-semibold">Last Modified:</span>
              <div className="text-gray-600 dark:text-gray-400">
                {formatDate(term.last_modified)}
              </div>
            </div>
            <div>
              <span className="font-semibold">Version:</span>
              <div className="text-gray-600 dark:text-gray-400">
                {term.version}
              </div>
            </div>
            {term.title_embedding && (
              <div>
                <span className="font-semibold">Title Embedding:</span>
                <div className="text-gray-600 dark:text-gray-400">
                  {term.title_embedding.length} dimensions
                </div>
              </div>
            )}
            {term.definition_embedding && (
              <div>
                <span className="font-semibold">Definition Embedding:</span>
                <div className="text-gray-600 dark:text-gray-400">
                  {term.definition_embedding.length} dimensions
                </div>
              </div>
            )}
          </div>
        </CsSidebarSection>
      </CsSidebar>

      <CsMain>
        <div className="mb-6 flex items-center justify-between">
          <div>
            <CsMainTitle icon={Hash}>{term.title}</CsMainTitle>
            <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center gap-1">
                <Hash className="h-4 w-4" />
                <span className="font-mono">{term.id}</span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                <span>Version {term.version}</span>
              </div>
            </div>
          </div>
          <Button color="gray" size="sm" onClick={() => setIsEditOpen(true)}>
            <Edit3 className="mr-2 h-4 w-4" />
            Edit
          </Button>
        </div>

        {/* Breadcrumb */}
        <div className="mb-4">
          <Breadcrumb aria-label="Term lineage breadcrumb">
            {/* Layer */}
            {layer && !layerLoading && (
              <BreadcrumbItem
                href={`/app/nodes/layer/${layer.id}`}
                icon={Layers}
              >
                {layer.title}
              </BreadcrumbItem>
            )}

            {/* Domain */}
            {domain && !domainLoading && (
              <BreadcrumbItem
                href={`/app/nodes/domain/${domain.id}`}
                icon={Database}
              >
                {domain.title}
              </BreadcrumbItem>
            )}

            {/* Term lineage */}
            {hierarchyLoading ? (
              <BreadcrumbItem icon={Hash}>
                <Spinner size="sm" />
                <span className="ml-1">Loading lineage...</span>
              </BreadcrumbItem>
            ) : (
              (() => {
                // If 3 or fewer terms, show all
                if (termLineage.length <= 3) {
                  return termLineage.map((ancestorTerm, index) => {
                    const isLast = index === termLineage.length - 1;

                    return (
                      <BreadcrumbItem
                        key={ancestorTerm.id}
                        href={
                          isLast
                            ? undefined
                            : `/app/nodes/term/${ancestorTerm.id}`
                        }
                        icon={Hash}
                      >
                        {ancestorTerm.title}
                      </BreadcrumbItem>
                    );
                  });
                }

                // If more than 3 terms, show first, "...", and last
                const breadcrumbItems = [];

                // First term
                const firstTerm = termLineage[0];
                breadcrumbItems.push(
                  <BreadcrumbItem
                    key={firstTerm.id}
                    href={`/app/nodes/term/${firstTerm.id}`}
                    icon={Hash}
                  >
                    {firstTerm.title}
                  </BreadcrumbItem>,
                );

                // Ellipsis placeholder for intermediate terms
                breadcrumbItems.push(
                  <BreadcrumbItem key="ellipsis" icon={Hash}>
                    ...
                  </BreadcrumbItem>,
                );

                // Last term (current term)
                const lastTerm = termLineage[termLineage.length - 1];
                breadcrumbItems.push(
                  <BreadcrumbItem key={lastTerm.id} icon={Hash}>
                    {lastTerm.title}
                  </BreadcrumbItem>,
                );

                return breadcrumbItems;
              })()
            )}
          </Breadcrumb>
        </div>

        <div className="space-y-6">
          {/* NLP */}
          <NlpAnalysisPanel
            text={term.title}
            textTitle={"Title"}
            domainContext={
              domain
                ? {
                    title: domain.title,
                    definition: domain.definition || "",
                  }
                : null
            }
            parentTermContext={
              parentTerm
                ? {
                    title: parentTerm.title,
                    definition: parentTerm.definition || "",
                    relationshipPredicate: "child_of", // You may want to determine this from actual relationship data
                  }
                : null
            }
            currentDefinition={term.definition}
            termId={term.id}
          />

          {/* Definition */}
          <Card>
            <h2 className="mb-3 text-xl font-semibold">Definition</h2>
            <p className="leading-relaxed text-gray-700 dark:text-gray-300">
              {term.definition}
            </p>
          </Card>

          {/* Term Hierarchy */}
          <Card>
            <h2 className="text-xl font-semibold">Term Hierarchy</h2>
            <TreeChartPanel termId={term.id} />
          </Card>

          {/* Child Terms */}
          <Card>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Child Terms</h2>
              <div className="flex items-center gap-2">
                <Badge color="gray" size="sm">
                  {childTerms?.length || 0} terms
                </Badge>
                <CreateChildButton
                  parentType="term"
                  parentId={term.id}
                  parentObject={term}
                  childType="term"
                />
              </div>
            </div>

            {childTermsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Spinner size="md" />
                <span className="ml-2">Loading child terms...</span>
              </div>
            ) : !childTerms || childTerms.length === 0 ? (
              <p className="text-gray-500 italic dark:text-gray-400">
                No child terms found for this term.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {childTerms.map((childTerm) => (
                  <div
                    key={childTerm.id}
                    className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700"
                  >
                    <div className="flex items-center">
                      <TermRenderer term_id={childTerm.id} />
                      <RouterLink
                        to="/app/nodes/term/$termId"
                        params={{ termId: childTerm.id }}
                        className="hover:text-primary-600 dark:hover:text-primary-300 ml-2 text-gray-400 transition-colors"
                      >
                        <CircleArrowRight className="h-4 w-4" />
                      </RouterLink>
                    </div>
                    {childTerm.definition && (
                      <p className="mt-2 line-clamp-2 text-sm text-gray-600 dark:text-gray-400">
                        {childTerm.definition}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Relationships */}
          <Card>
            <h2 className="mb-4 text-xl font-semibold">Relationships</h2>
            {relationshipsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Spinner size="md" />
                <span className="ml-2">Loading relationships...</span>
              </div>
            ) : Object.keys(relationshipsByPredicate).length === 0 ? (
              <p className="text-gray-500 italic dark:text-gray-400">
                No relationships found for this term.
              </p>
            ) : (
              <div className="space-y-4">
                {Object.entries(relationshipsByPredicate).map(
                  ([predicate, rels]) => (
                    <div
                      key={predicate}
                      className="rounded-lg border p-4 dark:border-gray-600"
                    >
                      <h3 className="mb-3 flex items-center gap-2 text-lg font-medium">
                        <Link className="h-4 w-4" />
                        {predicate}
                      </h3>

                      {/* Outgoing relationships (this term as source) */}
                      {rels.asSource.length > 0 && (
                        <div className="mb-3">
                          <h4 className="mb-2 text-sm font-medium text-gray-600 dark:text-gray-400">
                            → Outgoing ({rels.asSource.length})
                          </h4>
                          <RelationshipTermsDisplay
                            relationships={rels.asSource}
                            currentTermId={term.id}
                            direction="outgoing"
                            color="blue"
                          />
                        </div>
                      )}

                      {/* Incoming relationships (this term as target) */}
                      {rels.asTarget.length > 0 && (
                        <div>
                          <h4 className="mb-2 text-sm font-medium text-gray-600 dark:text-gray-400">
                            ← Incoming ({rels.asTarget.length})
                          </h4>
                          <RelationshipTermsDisplay
                            relationships={rels.asTarget}
                            currentTermId={term.id}
                            direction="incoming"
                            color="green"
                          />
                        </div>
                      )}
                    </div>
                  ),
                )}
              </div>
            )}
          </Card>
        </div>
      </CsMain>
      <TermEditModal
        term={term}
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
      />
    </>
  );
};

// Edit Modal for Term
const TermEditModal: React.FC<{
  term: StructureNode;
  isOpen: boolean;
  onClose: () => void;
}> = ({ term, isOpen, onClose }) => {
  const queryClient = useQueryClient();

  const handleSuccess = (updated: any) => {
    onClose();

    try {
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES, term.id],
      });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.STRUCTURE_NODES] });
    } catch (e) {
      console.warn("Failed to invalidate term queries", e);
    }
  };

  return (
    <Modal show={isOpen} onClose={onClose} size="lg">
      <ModalHeader className="border-b-0">Edit Term</ModalHeader>
      <ModalBody>
        <TermForm term={term} onSuccess={handleSuccess} />
      </ModalBody>
    </Modal>
  );
};

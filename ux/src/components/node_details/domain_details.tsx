import React from "react";
import { Card, Spinner, Button, Badge } from "flowbite-react";
import {
  Calendar,
  Hash,
  Edit3,
  Database,
  FileText,
  Layers,
  ExternalLink,
  CircleArrowRight,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useLayer } from "@/api/hooks/layers/useLayers";
import { useTerms } from "@/api/hooks/terms/useTerms";
import { TermRenderer } from "@/components/node_renderers/term_renderer";
import {
  CsSidebar,
  CsSidebarTitle,
  CsSidebarSection,
  CsSidebarSectionTitle,
} from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import type { components } from "@/api/client/types";

type DomainOut = components["schemas"]["DomainOut"];
type TermOut = components["schemas"]["TermOut"];

interface DomainDetailsProps {
  domain: DomainOut;
}

export const DomainDetails: React.FC<DomainDetailsProps> = ({ domain }) => {
  const { data: layer, isLoading: layerLoading } = useLayer(domain.layer_id);
  const { data: terms, isLoading: termsLoading } = useTerms({
    domain_id: domain.id,
  });

  // Group terms by parent-child relationships
  const { parentTerms, childTerms, rootTerms } = React.useMemo(() => {
    if (!terms) return { parentTerms: [], childTerms: [], rootTerms: [] };

    const parentTerms: TermOut[] = [];
    const childTerms: TermOut[] = [];
    const rootTerms: TermOut[] = [];

    terms.forEach((term: TermOut) => {
      if (term.parent_term_id) {
        // This term has a parent, so it's a child term
        childTerms.push(term);
      } else {
        // This term has no parent, so it's a root term
        rootTerms.push(term);
      }

      // Check if this term is a parent of any other terms
      const isParent = terms.some((t) => t.parent_term_id === term.id);
      if (isParent && !parentTerms.find((p) => p.id === term.id)) {
        parentTerms.push(term);
      }
    });

    return { parentTerms, childTerms, rootTerms };
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

        {/* Layer Information */}
        <CsSidebarSection>
          <CsSidebarSectionTitle icon={Layers}>Layer</CsSidebarSectionTitle>
          {layerLoading ? (
            <Spinner size="sm" />
          ) : layer ? (
            <div className="mx-2">
              <div className="flex items-center">
                <div className="font-semibold">{layer.title}</div>
                <Link
                  to="/app/nodes/layer/$layerId"
                  params={{ layerId: layer.id }}
                  className="hover:text-primary-600 dark:hover:text-primary-300 ml-2 text-gray-400 transition-colors"
                >
                  <CircleArrowRight className="h-4 w-4" />
                </Link>
              </div>
              {layer.definition && (
                <div className="text-sm mt-2 text-gray-600 dark:text-gray-400">
                  {layer.definition}
                </div>
              )}
            </div>
          ) : (
            <span className="text-gray-500 italic">Unknown layer</span>
          )}
        </CsSidebarSection>

        {/* Statistics */}
        <CsSidebarSection>
          <CsSidebarSectionTitle icon={FileText}>
            Statistics
          </CsSidebarSectionTitle>
          <div className="mx-2 space-y-2 inline-block">
            <div className="flex justify-between">
              <span className="text-sm">Total Terms:</span>
              <span className="font-semibold pl-2">{terms?.length || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">Root Terms:</span>
              <span className="font-semibold pl-2">{rootTerms.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">Parent Terms:</span>
              <span className="font-semibold pl-2">{parentTerms.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">Child Terms:</span>
              <span className="font-semibold pl-2">{childTerms.length}</span>
            </div>
          </div>
        </CsSidebarSection>

        <CsSidebarTitle>Metadata</CsSidebarTitle>
        <CsSidebarSection>
          <div className="mx-2 space-y-2">
            <div>
              <span className="font-semibold">Created:</span>
              <div className="text-gray-600 dark:text-gray-400">
                {formatDate(domain.created_at)}
              </div>
            </div>
            {domain.last_modified && (
              <div>
                <span className="font-semibold">Last Modified:</span>
                <div className="text-gray-600 dark:text-gray-400">
                  {formatDate(domain.last_modified)}
                </div>
              </div>
            )}
            <div>
              <span className="font-semibold">Version:</span>
              <div className="text-gray-600 dark:text-gray-400">
                {domain.version || 1}
              </div>
            </div>
            {domain.title_embedding && (
              <div>
                <span className="font-semibold">Title Embedding:</span>
                <div className="text-gray-600 dark:text-gray-400">
                  {domain.title_embedding.length} dimensions
                </div>
              </div>
            )}
            {domain.definition_embedding && (
              <div>
                <span className="font-semibold">Definition Embedding:</span>
                <div className="text-gray-600 dark:text-gray-400">
                  {domain.definition_embedding.length} dimensions
                </div>
              </div>
            )}
          </div>
        </CsSidebarSection>
      </CsSidebar>

      <CsMain>
        <div className="mb-6 flex items-center justify-between">
          <div>
            <CsMainTitle icon={Database}>
              {domain.title}
            </CsMainTitle>
            <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center gap-1">
                <Hash className="h-4 w-4" />
                <span className="font-mono">{domain.id}</span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                <span>Version {domain.version || 1}</span>
              </div>
            </div>
          </div>
          <Button color="gray" size="sm">
            <Edit3 className="mr-2 h-4 w-4" />
            Edit
          </Button>
        </div>

        <div className="space-y-6">
          {/* Definition */}
          <Card>
            <h2 className="mb-3 text-xl font-semibold">Definition</h2>
            <p className="leading-relaxed text-gray-700 dark:text-gray-300">
              {domain.definition}
            </p>
          </Card>

          {/* Terms in this Domain */}
          <Card>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Terms in this Domain</h2>
              <Badge color="gray" size="sm">
                {terms?.length || 0} terms
              </Badge>
            </div>

            {termsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Spinner size="md" />
                <span className="ml-2">Loading terms...</span>
              </div>
            ) : !terms || terms.length === 0 ? (
              <p className="text-gray-500 italic dark:text-gray-400">
                No terms found in this domain.
              </p>
            ) : (
              <div className="space-y-6">
                {/* Root Terms */}
                {rootTerms.length > 0 && (
                  <div>
                    <h3 className="mb-3 flex items-center gap-2 text-lg font-medium">
                      <Hash className="h-4 w-4" />
                      Root Terms
                      <Badge color="gray" size="sm">
                        {rootTerms.length}
                      </Badge>
                    </h3>
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      {rootTerms.map((term) => (
                        <div
                          key={term.id}
                          className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700"
                        >
                          <div className="flex items-center">
                            <TermRenderer term_id={term.id} />
                            <Link
                              to="/app/nodes/term/$termId"
                              params={{ termId: term.id }}
                            >
                              <CircleArrowRight className="hover:text-primary-600 dark:hover:text-primary-300 ml-2 inline h-4 w-4 text-gray-400 transition-colors" />
                            </Link>
                          </div>
                          {term.definition && (
                            <p className="mt-2 line-clamp-2 text-sm text-gray-600 dark:text-gray-400">
                              {term.definition}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Terms with Children */}
                {parentTerms.length > 0 && (
                  <div>
                    <h3 className="mb-3 flex items-center gap-2 text-lg font-medium">
                      <Hash className="h-4 w-4" />
                      Parent Terms
                      <Badge color="gray" size="sm">
                        {parentTerms.length}
                      </Badge>
                    </h3>
                    <div className="space-y-4">
                      {parentTerms.map((parentTerm) => {
                        const children = terms.filter(
                          (t) => t.parent_term_id === parentTerm.id,
                        );
                        return (
                          <div
                            key={parentTerm.id}
                            className="rounded-lg border p-4 dark:border-gray-600"
                          >
                            <div className="mb-3">
                              <div className="flex items-center">
                                <TermRenderer term_id={parentTerm.id} />
                                <Link
                                  to="/app/nodes/term/$termId"
                                  params={{ termId: parentTerm.id }}
                                >
                                  <CircleArrowRight className="hover:text-primary-600 dark:hover:text-primary-300 ml-2 inline h-4 w-4 text-gray-400 transition-colors" />
                                </Link>
                              </div>
                              {parentTerm.definition && (
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                  {parentTerm.definition}
                                </p>
                              )}
                            </div>
                            <div>
                              <h4 className="mb-2 text-sm font-medium text-gray-600 dark:text-gray-400">
                                Child Terms ({children.length})
                              </h4>
                              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                                {children.map((child) => (
                                  <div
                                    key={child.id}
                                    className="rounded-lg bg-gray-50 p-2 dark:bg-gray-700"
                                  >
                                    <div className="flex items-center">
                                      <TermRenderer term_id={child.id} />
                                      <Link
                                        to="/app/nodes/term/$termId"
                                        params={{ termId: child.id }}
                                      >
                                        <CircleArrowRight className="hover:text-primary-600 dark:hover:text-primary-300 ml-2 inline h-4 w-4 text-gray-400 transition-colors" />
                                      </Link>
                                    </div>
                                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                      {child.definition}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Orphaned Child Terms (have parent_term_id but parent not in this domain) */}
                {childTerms.filter(
                  (child) =>
                    !parentTerms.some((p) => p.id === child.parent_term_id),
                ).length > 0 && (
                  <div>
                    <h3 className="mb-3 flex items-center gap-2 text-lg font-medium">
                      <Hash className="h-4 w-4" />
                      Other Terms
                      <Badge color="gray" size="sm">
                        {
                          childTerms.filter(
                            (child) =>
                              !parentTerms.some(
                                (p) => p.id === child.parent_term_id,
                              ),
                          ).length
                        }
                      </Badge>
                    </h3>
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      {childTerms
                        .filter(
                          (child) =>
                            !parentTerms.some(
                              (p) => p.id === child.parent_term_id,
                            ),
                        )
                        .map((term) => (
                          <div
                            key={term.id}
                            className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700"
                          >
                            <TermRenderer term_id={term.id} />
                            {term.definition && (
                              <p className="mt-2 line-clamp-2 text-sm text-gray-600 dark:text-gray-400">
                                {term.definition}
                              </p>
                            )}
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </CsMain>
    </>
  );
};

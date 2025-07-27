import React from "react";
import { Card, Spinner, Button, Badge } from "flowbite-react";
import {
  Calendar,
  Hash,
  Edit3,
  Database,
  FileText,
  Link2,
  ExternalLink,
  CircleArrowRight,
  Layers,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useDomain } from "@/api/hooks/domains/useDomains";
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

type LayerOut = components["schemas"]["LayerOut"];
type TermOut = components["schemas"]["TermOut"];

interface LayerDetailsProps {
  layer: LayerOut;
}

export const LayerDetails: React.FC<LayerDetailsProps> = ({ layer }) => {
  const { data: terms, isLoading: termsLoading } = useTerms({
    layer_id: layer.id,
  });

  // Group terms by domain for better organization
  const termsByDomain = React.useMemo(() => {
    if (!terms) return {};

    const grouped: Record<string, TermOut[]> = {};

    terms.forEach((term: TermOut) => {
      if (!grouped[term.domain_id]) {
        grouped[term.domain_id] = [];
      }
      grouped[term.domain_id].push(term);
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

        {/* Primary Predicate */}
        {layer.primary_predicate && (
          <CsSidebarSection>
            <CsSidebarSectionTitle icon={Link2}>
              Primary Predicate
            </CsSidebarSectionTitle>
            <div className="mx-2">
              <Badge color="blue">{layer.primary_predicate}</Badge>
            </div>
          </CsSidebarSection>
        )}

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
              <span className="pl-2 font-semibold">
                {Object.keys(termsByDomain).length}
              </span>
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
            {layer.title_embedding && (
              <div>
                <span className="font-semibold">Title Embedding:</span>
                <div className="text-gray-600 dark:text-gray-400">
                  {layer.title_embedding.length} dimensions
                </div>
              </div>
            )}
            {layer.definition_embedding && (
              <div>
                <span className="font-semibold">Definition Embedding:</span>
                <div className="text-gray-600 dark:text-gray-400">
                  {layer.definition_embedding.length} dimensions
                </div>
              </div>
            )}
          </div>
        </CsSidebarSection>
      </CsSidebar>

      <CsMain>
        <div className="mb-6 flex items-center justify-between">
          <div>
            <CsMainTitle icon={Layers}>
              {layer.title}
            </CsMainTitle>
            <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center gap-1">
                <span className="font-mono">{layer.id}</span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                <span>Version {layer.version || 1}</span>
              </div>
              {layer.primary_predicate && (
                <div className="flex items-center gap-1">
                  <Link2 className="h-4 w-4" />
                  <Badge color="blue" size="sm">
                    {layer.primary_predicate}
                  </Badge>
                </div>
              )}
            </div>
          </div>
          <Button color="gray" size="sm">
            <Edit3 className="mr-2 h-4 w-4" />
            Edit
          </Button>
        </div>

        <div className="space-y-6">
          {/* Definition */}
          {layer.definition && (
            <Card>
              <h2 className="mb-3 text-xl font-semibold">Definition</h2>
              <p className="leading-relaxed text-gray-700 dark:text-gray-300">
                {layer.definition}
              </p>
            </Card>
          )}

          {/* Domains in this Layer */}
          <Card>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Domains in this Layer</h2>
              <Badge color="info" size="sm">
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
                No terms found in this layer.
              </p>
            ) : (
              <div className="space-y-4">
                {Object.entries(termsByDomain).map(
                  ([domainId, domainTerms]) => (
                    <DomainTermsSection
                      key={domainId}
                      domainId={domainId}
                      terms={domainTerms}
                    />
                  ),
                )}
              </div>
            )}
          </Card>
        </div>
      </CsMain>
    </>
  );
};

// Helper component to display terms grouped by domain
interface DomainTermsSectionProps {
  domainId: string;
  terms: TermOut[];
}

const DomainTermsSection: React.FC<DomainTermsSectionProps> = ({
  domainId,
  terms,
}) => {
  const { data: domain, isLoading: domainLoading } = useDomain(domainId);

  return (
    <div className="rounded-lg border p-4 dark:border-gray-600">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-medium">
          <Database className="h-4 w-4" />
          {domainLoading ? (
            <Spinner size="sm" />
          ) : domain ? (
            <div className="flex items-center gap-2">
              <Link
                to="/app/nodes/domain/$domainId"
                params={{ domainId: domain.id }}
                className="transition-colors hover:text-blue-600 dark:hover:text-blue-400"
              >
                {domain.title}
              </Link>
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
        <Badge color="gray" size="sm">
          {terms.length} terms
        </Badge>
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
              className="text-gray-400 ml-2 transition-colors hover:text-blue-600 dark:hover:text-blue-400"
            >
              <CircleArrowRight className="h-4 w-4" />
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
};

import React from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Card } from "flowbite-react";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";
import { CsMain, CsMainTitle } from "@/components/layout/cs_main";
import { Search, GitBranch, TestTube, ChevronRight } from "lucide-react";

export const Route = createFileRoute("/app/reference/")({
  component: ReferenceIndexPage,
});

function ReferenceIndexPage() {
  const referenceTools = [
    {
      title: "Knowledge Search",
      description:
        "Search external knowledge sources including ConceptNet, DBpedia, and Wikidata",
      icon: Search,
      path: "/app/reference/search",
    },
    {
      title: "Predicate Mapping",
      description:
        "Map internal predicates to external ontologies and knowledge bases",
      icon: GitBranch,
      path: "/app/reference/predicates",
    },
    {
      title: "RAG Testing",
      description:
        "Test and evaluate RAG pipelines with external reference data",
      icon: TestTube,
      path: "/app/reference/rag-test",
    },
  ];

  return (
    <>
      <CsSidebar>
        <CsSidebarTitle>External Reference</CsSidebarTitle>
      </CsSidebar>
      <CsMain>
        <CsMainTitle>External Reference Tools</CsMainTitle>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Integrate and query external knowledge sources to enrich your
          knowledge graph
        </p>

        <div className="mt-6 space-y-4">
          {referenceTools.map((tool) => (
            <Link key={tool.path} to={tool.path} className="block w-full">
              <div className="group rounded-lg border border-gray-200 p-4 transition-all hover:border-blue-300 hover:bg-blue-50 dark:border-gray-700 dark:hover:border-blue-600 dark:hover:bg-blue-900/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="text-2xl">
                      <tool.icon className="h-8 w-8 text-gray-600 group-hover:text-blue-600 dark:text-gray-400 dark:group-hover:text-blue-400" />
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900 group-hover:text-blue-600 dark:text-white dark:group-hover:text-blue-400">
                        {tool.title}
                      </h4>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {tool.description}
                      </p>
                    </div>
                  </div>
                  <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-blue-600 dark:group-hover:text-blue-400" />
                </div>
              </div>
            </Link>
          ))}
        </div>

        <div className="mt-6 rounded-lg bg-gray-50 p-4 dark:bg-gray-800">
          <div className="flex items-start gap-3">
            <Search className="mt-0.5 h-5 w-5 flex-shrink-0 text-gray-600 dark:text-gray-400" />
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                About External Reference
              </p>
              <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                External reference tools allow you to connect your local
                knowledge graph with established ontologies and knowledge bases
                like ConceptNet, DBpedia, and Wikidata. Use these tools to
                discover related concepts, validate terminology, and enhance
                your graph with rich semantic connections.
              </p>
            </div>
          </div>
        </div>
      </CsMain>
    </>
  );
}

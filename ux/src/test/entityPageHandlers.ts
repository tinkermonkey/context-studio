/**
 * MSW handlers serving a tiny ontology for the entity page tests:
 * taxonomy "tax-1" → scheme "scheme-1" → classes "class-1" (Component) and
 * "class-2" (Service); individuals "ind-1" (Router, a Component) and "ind-2"
 * (API, a Service); "prop-1" realizes Component → Service; "rel-1" Router → API.
 */
import { http, HttpResponse } from "msw";
import {
  createClass,
  createConceptScheme,
  createIndividual,
  createPropertyDefinition,
  createRelationship,
  createTaxonomy,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";

export const taxonomy = createTaxonomy({
  id: "tax-1",
  identifier: "dr_spec",
  title: "Documentation Robotics",
  description: "Architecture ontology",
  vision: "# Design charter\n\nAn element is a named architectural fact.",
});
export const scheme = createConceptScheme({
  id: "scheme-1",
  taxonomy_id: "tax-1",
  identifier: "application",
  title: "Application Layer",
  description: "Application layer",
});
export const component = createClass({
  id: "class-1",
  concept_scheme_id: "scheme-1",
  taxonomy_id: "tax-1",
  identifier: "application_component",
  title: "ApplicationComponent",
  description: "Modular, deployable part of a system",
  external_references: [{ source: "documentation_robotics", identifier: "application.component" }],
});
export const serviceClass = createClass({
  id: "class-2",
  concept_scheme_id: "scheme-1",
  taxonomy_id: "tax-1",
  identifier: "application_service",
  title: "ApplicationService",
  description: "Exposed behavior",
});
export const router = createIndividual({
  id: "ind-1",
  title: "LLM Provider Router",
  description: "Routes completion requests",
  class_ids: ["class-1"],
  data_properties: [{ property_identifier: "language", value: "python", datatype: "string" }],
  external_references: [{ source: "documentation_robotics", identifier: "app.router" }],
});
export const api = createIndividual({
  id: "ind-2",
  title: "Pipeline API",
  description: "Pipeline service",
  class_ids: ["class-2"],
});
export const realizes = createPropertyDefinition({
  id: "prop-1",
  identifier: "component_realizes_service",
  title: "application.component realizes application.service",
  canonical_predicate: "realizes",
  domain_class_id: "class-1",
  range_class_id: "class-2",
});
export const relationship = createRelationship({
  id: "rel-1",
  source_id: "ind-1",
  target_id: "ind-2",
  property_definition_id: "prop-1",
});

const classes = [component, serviceClass];
const individuals = [router, api];

function list<T>(items: T[]) {
  return HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });
}

function byIds<T extends { id: string }>(items: T[], url: URL): T[] {
  const ids = url.searchParams.getAll("ids");
  return ids.length ? items.filter((item) => ids.includes(item.id)) : items;
}

export const entityPageHandlers = [
  http.get("*/api/taxonomies/:id/scheme-counts", () =>
    HttpResponse.json([
      {
        scheme_id: "scheme-1",
        class_count: 2,
        individual_count: 2,
        property_definition_count: 1,
      },
    ]),
  ),
  http.get("*/api/taxonomies/:id", ({ params }) =>
    params.id === "tax-1"
      ? HttpResponse.json(taxonomy)
      : HttpResponse.json({ detail: "Taxonomy not found" }, { status: 404 }),
  ),
  http.get("*/api/taxonomies", () => list([taxonomy])),
  http.get("*/api/schemes/:id/class-counts", () =>
    HttpResponse.json([
      {
        class_id: "class-1",
        individual_count: 1,
        property_definition_count: 1,
        relationship_count: 1,
      },
      {
        class_id: "class-2",
        individual_count: 1,
        property_definition_count: 0,
        relationship_count: 0,
      },
    ]),
  ),
  http.get("*/api/schemes/:id", () => HttpResponse.json(scheme)),
  http.get("*/api/schemes", () => list([scheme])),
  http.get("*/api/classes/:id/attribute-definitions", () => list([])),
  http.get("*/api/classes/:id", ({ params }) => {
    const cls = classes.find((c) => c.id === params.id);
    return cls
      ? HttpResponse.json(cls)
      : HttpResponse.json({ detail: "Class not found" }, { status: 404 });
  }),
  http.get("*/api/classes", ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get("q")?.toLowerCase();
    const schemeId = url.searchParams.get("concept_scheme_id");
    return list(
      byIds(classes, url).filter(
        (c) =>
          (!q || c.title.toLowerCase().includes(q)) &&
          (!schemeId || c.concept_scheme_id === schemeId),
      ),
    );
  }),
  http.get("*/api/individuals/:id", ({ params }) => {
    const ind = individuals.find((i) => i.id === params.id);
    return ind
      ? HttpResponse.json(ind)
      : HttpResponse.json({ detail: "Individual not found" }, { status: 404 });
  }),
  http.get("*/api/individuals", ({ request }) => {
    const url = new URL(request.url);
    const classId = url.searchParams.get("class_id");
    const q = url.searchParams.get("q")?.toLowerCase();
    const items = byIds(individuals, url).filter(
      (i) =>
        (!classId || i.class_ids.includes(classId)) && (!q || i.title.toLowerCase().includes(q)),
    );
    return list(items);
  }),
  http.get("*/api/properties", ({ request }) => {
    const url = new URL(request.url);
    const domain = url.searchParams.get("domain_class_id");
    return list(byIds([realizes], url).filter((p) => !domain || p.domain_class_id === domain));
  }),
  http.get("*/api/relationships", ({ request }) => {
    const url = new URL(request.url);
    const source = url.searchParams.get("source_id");
    const target = url.searchParams.get("target_id");
    return list(
      [relationship].filter(
        (r) => (!source || r.source_id === source) && (!target || r.target_id === target),
      ),
    );
  }),
];

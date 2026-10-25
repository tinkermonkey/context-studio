import { BaseService } from "./base";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type TaxonomyCreateRequest = components["schemas"]["TaxonomyCreateRequest"];
type TaxonomyUpdateRequest = components["schemas"]["TaxonomyUpdateRequest"];
type ListTaxonomies = components["schemas"]["ListResponse_TaxonomyResponse_"];

type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];
type ConceptSchemeCreateRequest = components["schemas"]["ConceptSchemeCreateRequest"];
type ConceptSchemeUpdateRequest = components["schemas"]["ConceptSchemeUpdateRequest"];
type ListSchemes = components["schemas"]["ListResponse_ConceptSchemeResponse_"];

type ClassResponse = components["schemas"]["ClassResponse"];
type ClassCreateRequest = components["schemas"]["ClassCreateRequest"];
type ClassUpdateRequest = components["schemas"]["ClassUpdateRequest"];
type ClassMoveRequest = components["schemas"]["ClassMoveRequest"];
type ListClasses = components["schemas"]["ListResponse_ClassResponse_"];
type ListAttributeDefinitions = components["schemas"]["ListResponse_AttributeDefinitionResponse_"];

type IndividualResponse = components["schemas"]["IndividualResponse"];
type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualUpdateRequest = components["schemas"]["IndividualUpdateRequest"];
type IndividualClassRequest = components["schemas"]["IndividualClassRequest"];
type IndividualClassListRequest = components["schemas"]["IndividualClassListRequest"];
type ListIndividuals = components["schemas"]["ListResponse_IndividualResponse_"];

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];
type PropertyDefinitionCreateRequest = components["schemas"]["PropertyDefinitionCreateRequest"];
type PropertyDefinitionUpdateRequest = components["schemas"]["PropertyDefinitionUpdateRequest"];
type ListProperties = components["schemas"]["ListResponse_PropertyDefinitionResponse_"];

type RelationshipResponse = components["schemas"]["RelationshipResponse"];
type RelationshipCreateRequest = components["schemas"]["RelationshipCreateRequest"];
type ListRelationships = components["schemas"]["ListResponse_RelationshipResponse_"];

type SchemeCountsResponse = components["schemas"]["SchemeCountsResponse"];
type ClassCountsResponse = components["schemas"]["ClassCountsResponse"];

/** Paging, text search and sort params shared by the list endpoints. */
export interface ListPageParams {
  limit?: number;
  offset?: number;
  /** Case-insensitive "title or identifier contains" search. */
  q?: string;
  sort_by?: "title" | "created_at" | "last_modified";
  sort_order?: "asc" | "desc";
}

/** Restrict a list to these ids (sent as repeated `ids=` params; backend cap 500). */
export interface IdsFilterParams {
  ids?: string[];
}

export interface ClassListParams extends ListPageParams, IdsFilterParams {
  concept_scheme_id?: string;
  parent_class_id?: string;
}

export interface IndividualListParams extends ListPageParams, IdsFilterParams {
  class_id?: string;
}

export interface PropertyListParams extends ListPageParams, IdsFilterParams {
  /** Only property definitions with this class as domain. */
  domain_class_id?: string;
}

export interface RelationshipListParams extends Omit<ListPageParams, "sort_by"> {
  source_id?: string;
  target_id?: string;
  property_id?: string;
  /** Relationships only sort by creation time. */
  sort_by?: "created_at";
}

class OntologyService extends BaseService {
  // Taxonomies
  async listTaxonomies(params?: ListPageParams): Promise<ListTaxonomies> {
    return this.get<ListTaxonomies>("/api/taxonomies", params as Record<string, unknown>);
  }

  async getTaxonomy(id: string): Promise<TaxonomyResponse> {
    return this.get<TaxonomyResponse>(`/api/taxonomies/${id}`);
  }

  async createTaxonomy(data: TaxonomyCreateRequest): Promise<TaxonomyResponse> {
    return this.post<TaxonomyResponse>("/api/taxonomies", data);
  }

  async updateTaxonomy(id: string, data: TaxonomyUpdateRequest): Promise<TaxonomyResponse> {
    return this.put<TaxonomyResponse>(`/api/taxonomies/${id}`, data);
  }

  async deleteTaxonomy(id: string): Promise<void> {
    return this.delete<void>(`/api/taxonomies/${id}`);
  }

  async getPublishDiffStats(id: string): Promise<components["schemas"]["PublishDiffStats"]> {
    return this.get<components["schemas"]["PublishDiffStats"]>(
      `/api/taxonomies/${id}/publish-diff`,
    );
  }

  async publishTaxonomy(id: string, commitMessage: string): Promise<TaxonomyResponse> {
    return this.post<TaxonomyResponse>(`/api/taxonomies/${id}/publish`, {
      commit_message: commitMessage,
    });
  }

  /** Class, individual and property-definition counts for each scheme in a taxonomy. */
  async getSchemeCounts(taxonomyId: string): Promise<SchemeCountsResponse[]> {
    return this.get<SchemeCountsResponse[]>(`/api/taxonomies/${taxonomyId}/scheme-counts`);
  }

  // Concept Schemes
  async listSchemes(taxonomyId?: string, params?: ListPageParams): Promise<ListSchemes> {
    const query = { ...(taxonomyId ? { taxonomy_id: taxonomyId } : {}), ...params };
    return this.get<ListSchemes>("/api/schemes", Object.keys(query).length ? query : undefined);
  }

  async getScheme(id: string): Promise<ConceptSchemeResponse> {
    return this.get<ConceptSchemeResponse>(`/api/schemes/${id}`);
  }

  async createScheme(
    taxonomyId: string,
    data: ConceptSchemeCreateRequest,
  ): Promise<ConceptSchemeResponse> {
    return this.post<ConceptSchemeResponse>(`/api/taxonomies/${taxonomyId}/schemes`, data);
  }

  async updateScheme(id: string, data: ConceptSchemeUpdateRequest): Promise<ConceptSchemeResponse> {
    return this.put<ConceptSchemeResponse>(`/api/schemes/${id}`, data);
  }

  async deleteScheme(id: string): Promise<void> {
    return this.delete<void>(`/api/schemes/${id}`);
  }

  /** Individual, property-definition and relationship counts for each class in a scheme. */
  async getClassCounts(schemeId: string): Promise<ClassCountsResponse[]> {
    return this.get<ClassCountsResponse[]>(`/api/schemes/${schemeId}/class-counts`);
  }

  // Classes
  async listClasses(params?: ClassListParams): Promise<ListClasses> {
    return this.get<ListClasses>("/api/classes", params as Record<string, unknown>);
  }

  async getClass(id: string): Promise<ClassResponse> {
    return this.get<ClassResponse>(`/api/classes/${id}`);
  }

  async listClassAttributeDefinitions(
    classId: string,
    params?: Pick<ListPageParams, "limit" | "offset">,
  ): Promise<ListAttributeDefinitions> {
    return this.get<ListAttributeDefinitions>(
      `/api/classes/${classId}/attribute-definitions`,
      params as Record<string, unknown>,
    );
  }

  async createClass(schemeId: string, data: ClassCreateRequest): Promise<ClassResponse> {
    return this.post<ClassResponse>(`/api/schemes/${schemeId}/classes`, data);
  }

  async updateClass(id: string, data: ClassUpdateRequest): Promise<ClassResponse> {
    return this.put<ClassResponse>(`/api/classes/${id}`, data);
  }

  async moveClass(id: string, data: ClassMoveRequest): Promise<ClassResponse> {
    return this.post<ClassResponse>(`/api/classes/${id}/move`, data);
  }

  async deleteClass(id: string): Promise<void> {
    return this.delete<void>(`/api/classes/${id}`);
  }

  // Individuals
  async listIndividuals(params?: IndividualListParams): Promise<ListIndividuals> {
    return this.get<ListIndividuals>("/api/individuals", params as Record<string, unknown>);
  }

  async getIndividual(id: string): Promise<IndividualResponse> {
    return this.get<IndividualResponse>(`/api/individuals/${id}`);
  }

  async createIndividual(data: IndividualCreateRequest): Promise<IndividualResponse> {
    return this.post<IndividualResponse>("/api/individuals", data);
  }

  async updateIndividual(id: string, data: IndividualUpdateRequest): Promise<IndividualResponse> {
    return this.put<IndividualResponse>(`/api/individuals/${id}`, data);
  }

  async deleteIndividual(id: string): Promise<void> {
    return this.delete<void>(`/api/individuals/${id}`);
  }

  async addParentClass(
    individualId: string,
    data: IndividualClassRequest,
  ): Promise<IndividualResponse> {
    return this.post<IndividualResponse>(`/api/individuals/${individualId}/classes`, data);
  }

  async removeParentClass(individualId: string, classId: string): Promise<void> {
    return this.delete<void>(`/api/individuals/${individualId}/classes/${classId}`);
  }

  async reorderIndividualClasses(
    individualId: string,
    data: IndividualClassListRequest,
  ): Promise<IndividualResponse> {
    return this.put<IndividualResponse>(`/api/individuals/${individualId}/classes`, data);
  }

  async getIndividualInheritedProperties(
    individualId: string,
  ): Promise<components["schemas"]["ListResponse_DataPropertyValueResponse_"]> {
    return this.get<components["schemas"]["ListResponse_DataPropertyValueResponse_"]>(
      `/api/individuals/${individualId}/inherited-properties`,
    );
  }

  // Property Definitions
  async listProperties(isRelevant?: boolean, params?: PropertyListParams): Promise<ListProperties> {
    const query = { ...(isRelevant !== undefined ? { is_relevant: isRelevant } : {}), ...params };
    return this.get<ListProperties>(
      "/api/properties",
      Object.keys(query).length ? query : undefined,
    );
  }

  async getProperty(id: string): Promise<PropertyDefinitionResponse> {
    return this.get<PropertyDefinitionResponse>(`/api/properties/${id}`);
  }

  async createProperty(data: PropertyDefinitionCreateRequest): Promise<PropertyDefinitionResponse> {
    return this.post<PropertyDefinitionResponse>("/api/properties", data);
  }

  async updateProperty(
    id: string,
    data: PropertyDefinitionUpdateRequest,
  ): Promise<PropertyDefinitionResponse> {
    return this.put<PropertyDefinitionResponse>(`/api/properties/${id}`, data);
  }

  async deleteProperty(id: string): Promise<void> {
    return this.delete<void>(`/api/properties/${id}`);
  }

  // Relationships
  async listRelationships(params?: RelationshipListParams): Promise<ListRelationships> {
    return this.get<ListRelationships>("/api/relationships", params as Record<string, unknown>);
  }

  async getRelationship(id: string): Promise<RelationshipResponse> {
    return this.get<RelationshipResponse>(`/api/relationships/${id}`);
  }

  async createRelationship(data: RelationshipCreateRequest): Promise<RelationshipResponse> {
    return this.post<RelationshipResponse>("/api/relationships", data);
  }

  async deleteRelationship(id: string): Promise<void> {
    return this.delete<void>(`/api/relationships/${id}`);
  }
}

export const ontologyService = new OntologyService();

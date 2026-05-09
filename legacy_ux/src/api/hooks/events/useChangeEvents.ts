/**
 * Change Events Query Hooks
 *
 * React Query hooks for the new change events system
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import { QUERY_KEYS, ENDPOINTS } from "../../config";
import { BaseService } from "../../services/base";
import {
  ChangeEvent,
  RecordType,
  NodeType,
  isOntologyClassEvent,
  isConceptSchemeEvent,
  isTaxonomyEvent,
  isRelationshipEvent,
  isPropertyDefinitionEvent,
} from "../../types/changeEvents";

// Change Events Service
class ChangeEventService extends BaseService {
  /**
   * List change events with optional filtering
   */
  async list(params?: {
    skip?: number;
    limit?: number;
    entity_type?: string;
    entity_id?: string;
    operation?: string;
    processed?: boolean;
  }): Promise<ChangeEvent[]> {
    return this.withErrorContext(async () => {
      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.entity_type) queryParams.entity_type = params.entity_type;
      if (params?.entity_id) queryParams.entity_id = params.entity_id;
      if (params?.operation) queryParams.operation = params.operation;
      if (params?.processed !== undefined)
        queryParams.processed = params.processed;

      const response = await this.getResource<{
        events: ChangeEvent[];
        total: number;
      }>(ENDPOINTS.CHANGE_EVENTS, queryParams);
      return response.events;
    }, "list");
  }

  /**
   * Get a specific change event by ID
   */
  async get(id: number): Promise<ChangeEvent> {
    return this.withErrorContext(async () => {
      return this.getResource<ChangeEvent>(`${ENDPOINTS.CHANGE_EVENTS}/${id}`);
    }, "get");
  }

  /**
   * Mark a change event as processed
   */
  async markProcessed(id: number): Promise<ChangeEvent> {
    return this.withErrorContext(async () => {
      return this.putResource<ChangeEvent>(`${ENDPOINTS.CHANGE_EVENTS}/${id}`, {
        processed: true,
      });
    }, "markProcessed");
  }

  /**
   * Get unprocessed change events
   */
  async getUnprocessed(params?: {
    entity_type?: string;
    limit?: number;
  }): Promise<ChangeEvent[]> {
    return this.list({ ...params, processed: false });
  }
}

// Export singleton instance
export const changeEventService = new ChangeEventService();

// Event query keys
export const changeEventQueryKeys = {
  all: [QUERY_KEYS.CHANGE_EVENTS] as const,
  lists: () => [...changeEventQueryKeys.all, "list"] as const,
  list: (params?: any) => [...changeEventQueryKeys.lists(), params] as const,
  details: () => [...changeEventQueryKeys.all, "detail"] as const,
  detail: (id: number) => [...changeEventQueryKeys.details(), id] as const,
  unprocessed: (entityType?: string) =>
    [...changeEventQueryKeys.all, "unprocessed", entityType] as const,
  byEntity: (entityType: string, entityId: string) =>
    [...changeEventQueryKeys.all, "byEntity", entityType, entityId] as const,
};

/**
 * Hook to fetch change events
 */
export const useChangeEvents = (
  params?: {
    skip?: number;
    limit?: number;
    entity_type?: string;
    entity_id?: string;
    operation?: string;
    processed?: boolean;
  },
  options?: UseQueryOptions<ChangeEvent[], Error>,
) => {
  return useQuery({
    queryKey: changeEventQueryKeys.list(params),
    queryFn: () => changeEventService.list(params),
    staleTime: 1000 * 30, // 30 seconds - events should be fresh
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to fetch a specific change event by ID
 */
export const useChangeEvent = (
  id: number,
  options?: UseQueryOptions<ChangeEvent, Error>,
) => {
  return useQuery({
    queryKey: changeEventQueryKeys.detail(id),
    queryFn: () => changeEventService.get(id),
    enabled: !!id,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to fetch unprocessed change events
 */
export const useUnprocessedChangeEvents = (
  entityType?: string,
  options?: UseQueryOptions<ChangeEvent[], Error>,
) => {
  return useQuery({
    queryKey: changeEventQueryKeys.unprocessed(entityType),
    queryFn: () =>
      changeEventService.getUnprocessed({ entity_type: entityType }),
    staleTime: 1000 * 10, // 10 seconds - unprocessed events should be very fresh
    refetchInterval: 1000 * 30, // Refetch every 30 seconds for real-time updates
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to fetch change events for a specific entity
 */
export const useChangeEventsByEntity = (
  entityType: string,
  entityId: string,
  options?: UseQueryOptions<ChangeEvent[], Error>,
) => {
  return useQuery({
    queryKey: changeEventQueryKeys.byEntity(entityType, entityId),
    queryFn: () =>
      changeEventService.list({ entity_type: entityType, entity_id: entityId }),
    enabled: !!entityType && !!entityId,
    staleTime: 1000 * 60 * 2, // 2 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

// Event processing utilities

/**
 * Process a change event and determine its routing
 */
export const processChangeEvent = (event: ChangeEvent) => {
  const routing = {
    entityType: event.entity_type,
    operation: event.operation,
    entityId: event.entity_id,
    isTaxonomy: isTaxonomyEvent(event),
    isConceptScheme: isConceptSchemeEvent(event),
    isOntologyClass: isOntologyClassEvent(event),
    isRelationship: isRelationshipEvent(event),
    isPropertyDefinition: isPropertyDefinitionEvent(event),
    nodeType: null as NodeType | null,
  };

  // For ontology class events, determine the specific node type
  if (isOntologyClassEvent(event)) {
    const nodeType =
      event.new_state?.node_type || event.previous_state?.node_type;
    routing.nodeType = nodeType as NodeType;
  }

  return routing;
};

// Event filtering utilities

/**
 * Filter events by node type
 */
export const filterEventsByNodeType = (
  events: ChangeEvent[],
  nodeType: NodeType,
): ChangeEvent[] => {
  return events.filter((event) => {
    if (!isOntologyClassEvent(event)) return false;
    const eventNodeType =
      event.new_state?.node_type || event.previous_state?.node_type;
    return eventNodeType === nodeType;
  });
};

/**
 * Filter events by entity type
 */
export const filterEventsByEntityType = (
  events: ChangeEvent[],
  entityType: string,
): ChangeEvent[] => {
  return events.filter((event) => event.entity_type === entityType);
};

/**
 * Get taxonomy events only
 */
export const getTaxonomyEvents = (events: ChangeEvent[]): ChangeEvent[] => {
  return filterEventsByEntityType(events, RecordType.TAXONOMY);
};

/**
 * Get concept scheme events only
 */
export const getConceptSchemeEvents = (
  events: ChangeEvent[],
): ChangeEvent[] => {
  return filterEventsByEntityType(events, RecordType.CONCEPT_SCHEME);
};

/**
 * Get ontology class events only
 */
export const getOntologyClassEvents = (
  events: ChangeEvent[],
): ChangeEvent[] => {
  return filterEventsByEntityType(events, RecordType.ONTOLOGY_CLASS);
};

/**
 * Get relationship events only
 */
export const getRelationshipEvents = (events: ChangeEvent[]): ChangeEvent[] => {
  return filterEventsByEntityType(events, RecordType.RELATIONSHIP);
};

/**
 * Get property definition events only
 */
export const getPropertyDefinitionEvents = (
  events: ChangeEvent[],
): ChangeEvent[] => {
  return filterEventsByEntityType(events, RecordType.PROPERTY_DEFINITION);
};

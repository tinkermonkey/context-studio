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
  isStructureNodeEvent,
  isStructureNodeLinkEvent,
  isPredicateEvent,
} from "../../types/structureNodes";

// Change Events Service
class ChangeEventService extends BaseService {
  /**
   * List change events with optional filtering
   */
  async list(params?: {
    skip?: number;
    limit?: number;
    record_type?: RecordType;
    record_id?: string;
    event_type?: string;
    processed?: boolean;
  }): Promise<ChangeEvent[]> {
    return this.withErrorContext(async () => {
      const url = ENDPOINTS.CHANGE_EVENTS + "/";

      // Build query parameters
      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.record_type) queryParams.record_type = params.record_type;
      if (params?.record_id) queryParams.record_id = params.record_id;
      if (params?.event_type) queryParams.event_type = params.event_type;
      if (params?.processed !== undefined)
        queryParams.processed = params.processed;

      // If limit is explicitly set, use single page request
      if (params?.limit !== undefined) {
        return this.getPage<ChangeEvent>(url, queryParams);
      }

      // Otherwise, load all events across all pages
      return this.getAllPaginated<ChangeEvent>(url, queryParams);
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
    record_type?: RecordType;
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
   
  list: (params?: any)  // eslint-disable-line @typescript-eslint/no-explicit-any
 => [...changeEventQueryKeys.lists(), params] as const,
  details: () => [...changeEventQueryKeys.all, "detail"] as const,
  detail: (id: number) => [...changeEventQueryKeys.details(), id] as const,
  unprocessed: (recordType?: RecordType) =>
    [...changeEventQueryKeys.all, "unprocessed", recordType] as const,
  byRecord: (recordType: RecordType, recordId: string) =>
    [...changeEventQueryKeys.all, "byRecord", recordType, recordId] as const,
};

/**
 * Hook to fetch change events
 */
export const useChangeEvents = (
  params?: {
    skip?: number;
    limit?: number;
    record_type?: RecordType;
    record_id?: string;
    event_type?: string;
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
  recordType?: RecordType,
  options?: UseQueryOptions<ChangeEvent[], Error>,
) => {
  return useQuery({
    queryKey: changeEventQueryKeys.unprocessed(recordType),
    queryFn: () =>
      changeEventService.getUnprocessed({ record_type: recordType }),
    staleTime: 1000 * 10, // 10 seconds - unprocessed events should be very fresh
    refetchInterval: 1000 * 30, // Refetch every 30 seconds for real-time updates
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to fetch change events for a specific record
 */
export const useChangeEventsByRecord = (
  recordType: RecordType,
  recordId: string,
  options?: UseQueryOptions<ChangeEvent[], Error>,
) => {
  return useQuery({
    queryKey: changeEventQueryKeys.byRecord(recordType, recordId),
    queryFn: () =>
      changeEventService.list({ record_type: recordType, record_id: recordId }),
    enabled: !!recordType && !!recordId,
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
    recordType: event.record_type,
    eventType: event.event_type,
    recordId: event.record_id,
    isStructureNode: isStructureNodeEvent(event),
    isNodeLink: isStructureNodeLinkEvent(event),
    isPredicate: isPredicateEvent(event),
    nodeType: null as NodeType | null,
  };

  // For structure node events, determine the specific node type
  if (isStructureNodeEvent(event)) {
    const nodeType = event.new_data?.node_type || event.old_data?.node_type;
    routing.nodeType = nodeType as NodeType;
  }

  return routing;
};

// Event filtering utilities

/**
 * Filter events by structure node type
 */
export const filterEventsByNodeType = (
  events: ChangeEvent[],
  nodeType: NodeType,
): ChangeEvent[] => {
  return events.filter((event) => {
    if (!isStructureNodeEvent(event)) return false;
    const eventNodeType =
      event.new_data?.node_type || event.old_data?.node_type;
    return eventNodeType === nodeType;
  });
};

/**
 * Filter events by record type
 */
export const filterEventsByRecordType = (
  events: ChangeEvent[],
  recordType: RecordType,
): ChangeEvent[] => {
  return events.filter((event) => event.record_type === recordType);
};

/**
 * Get structure node events only
 */
export const getStructureNodeEvents = (
  events: ChangeEvent[],
): ChangeEvent[] => {
  return filterEventsByRecordType(events, RecordType.STRUCTURE_NODE);
};

/**
 * Get node link events only
 */
export const getNodeLinkEvents = (events: ChangeEvent[]): ChangeEvent[] => {
  return filterEventsByRecordType(events, RecordType.STRUCTURE_NODE_LINK);
};

/**
 * Get predicate events only
 */
export const getPredicateEvents = (events: ChangeEvent[]): ChangeEvent[] => {
  return filterEventsByRecordType(events, RecordType.PREDICATE);
};

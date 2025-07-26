/**
 * Query Parameter Utilities
 * 
 * Utilities for working with TanStack Query parameters and filters
 */

import type { QueryFilter } from "@/components/misc/query_filters";

/**
 * Convert query filters to URL search parameters
 * This follows TanStack Query best practices by including all filter criteria in the query key
 */
export function filtersToQueryParams(filters: QueryFilter[]): Record<string, unknown> {
  const params: Record<string, unknown> = {};

  filters.forEach(filter => {
    if (filter.value === undefined || filter.value === null || filter.value === '') {
      return;
    }

    const { field, operator, value } = filter;

    switch (operator) {
      case 'equals':
        params[field] = value;
        break;
      
      case 'contains':
        params[`${field}_contains`] = value;
        break;
      
      case 'starts_with':
        params[`${field}_starts_with`] = value;
        break;
      
      case 'ends_with':
        params[`${field}_ends_with`] = value;
        break;
      
      case 'gt':
        params[`${field}_gt`] = value;
        break;
      
      case 'gte':
        params[`${field}_gte`] = value;
        break;
      
      case 'lt':
        params[`${field}_lt`] = value;
        break;
      
      case 'lte':
        params[`${field}_lte`] = value;
        break;
      
      case 'between':
        if (Array.isArray(value) && value.length === 2) {
          const [min, max] = value;
          if (min !== undefined && min !== null && min !== '') {
            params[`${field}_gte`] = min;
          }
          if (max !== undefined && max !== null && max !== '') {
            params[`${field}_lte`] = max;
          }
        }
        break;
      
      case 'in':
        if (Array.isArray(value)) {
          params[`${field}_in`] = value.join(',');
        } else {
          params[`${field}_in`] = value;
        }
        break;
    }
  });

  return params;
}

/**
 * Convert query parameters back to filters
 * Useful for initializing filter state from URL params or saved queries
 */
export function queryParamsToFilters(
  params: Record<string, unknown>, 
  fieldDefinitions: Array<{ field: string; label: string }>
): QueryFilter[] {
  const filters: QueryFilter[] = [];
  const processedFields = new Set<string>();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }

    // Skip common pagination/sorting params
    if (['query', 'skip', 'limit', 'sort', 'page', 'pageSize'].includes(key)) {
      return;
    }

    let field = key;
    let operator: QueryFilter['operator'] = 'equals';

    // Parse operator suffixes
    if (key.endsWith('_contains')) {
      field = key.slice(0, -9);
      operator = 'contains';
    } else if (key.endsWith('_starts_with')) {
      field = key.slice(0, -12);
      operator = 'starts_with';
    } else if (key.endsWith('_ends_with')) {
      field = key.slice(0, -10);
      operator = 'ends_with';
    } else if (key.endsWith('_gte')) {
      field = key.slice(0, -4);
      operator = 'gte';
    } else if (key.endsWith('_gt')) {
      field = key.slice(0, -3);
      operator = 'gt';
    } else if (key.endsWith('_lte')) {
      field = key.slice(0, -4);
      operator = 'lte';
    } else if (key.endsWith('_lt')) {
      field = key.slice(0, -3);
      operator = 'lt';
    } else if (key.endsWith('_in')) {
      field = key.slice(0, -3);
      operator = 'in';
    }

    // Find the field definition
    const fieldDef = fieldDefinitions.find(f => f.field === field);
    if (!fieldDef) {
      return; // Skip unknown fields
    }

    // Handle range queries (between operator)
    const gteKey = `${field}_gte`;
    const lteKey = `${field}_lte`;
    if (params[gteKey] !== undefined || params[lteKey] !== undefined) {
      if (!processedFields.has(`${field}_range`)) {
        const gteValue = params[gteKey];
        const lteValue = params[lteKey];
        filters.push({
          field,
          operator: 'between',
          value: [
            gteValue !== undefined ? String(gteValue) : '', 
            lteValue !== undefined ? String(lteValue) : ''
          ],
          label: fieldDef.label,
        });
        processedFields.add(`${field}_range`);
      }
      return;
    }

    // Handle 'in' operator with comma-separated values
    if (operator === 'in') {
      const values = typeof value === 'string' 
        ? value.split(',').map(v => v.trim()).filter(v => v) 
        : [String(value)];
      filters.push({
        field,
        operator,
        value: values,
        label: fieldDef.label,
      });
      return;
    }

    // Handle simple operators
    filters.push({
      field,
      operator,
      value: String(value),
      label: fieldDef.label,
    });
  });

  return filters;
}

/**
 * Create a TanStack Query key that includes filter parameters
 * This ensures the query will re-run when filters change
 */
export function createFilteredQueryKey(
  baseKey: unknown[],
  searchTerm?: string,
  filters?: QueryFilter[],
  otherParams?: Record<string, unknown>
): unknown[] {
  const key = [...baseKey];

  // Add search term if provided
  if (searchTerm && searchTerm.trim()) {
    key.push({ query: searchTerm.trim() });
  }

  // Add filter parameters
  if (filters && filters.length > 0) {
    const filterParams = filtersToQueryParams(filters);
    if (Object.keys(filterParams).length > 0) {
      key.push({ filters: filterParams });
    }
  }

  // Add other parameters
  if (otherParams && Object.keys(otherParams).length > 0) {
    key.push({ params: otherParams });
  }

  return key;
}

/**
 * Combine search, filters, and other parameters into a single params object
 * for API calls
 */
export function combineQueryParams(
  searchTerm?: string,
  filters?: QueryFilter[],
  otherParams?: Record<string, unknown>
): Record<string, unknown> {
  const params: Record<string, unknown> = { ...otherParams };

  // Add search term
  if (searchTerm && searchTerm.trim()) {
    params.query = searchTerm.trim();
  }

  // Add filter parameters
  if (filters && filters.length > 0) {
    const filterParams = filtersToQueryParams(filters);
    Object.assign(params, filterParams);
  }

  return params;
}

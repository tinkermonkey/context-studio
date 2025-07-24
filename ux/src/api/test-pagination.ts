/**
 * Test file to verify pagination API changes
 * This file demonstrates the new pagination functionality
 */

import { layerService } from './services/layers';
import { domainService } from './services/domains';
import { termService } from './services/terms';
import type { PaginatedResponse } from './services/base';
import type { components } from './client/types';

type LayerOut = components['schemas']['LayerOut'];
type DomainOut = components['schemas']['DomainOut'];
type TermOut = components['schemas']['TermOut'];

// Example usage of the new pagination API
export async function testPaginationFeatures() {
  try {
    // Test layers pagination with metadata
    const layersResponse: PaginatedResponse<LayerOut> = await layerService.listPageWithMetadata({
      skip: 0,
      limit: 10,
      sort: 'title'
    });

    console.log('Layers pagination response:', {
      totalItems: layersResponse.total,
      currentPage: layersResponse.skip / layersResponse.limit + 1,
      itemsPerPage: layersResponse.limit,
      itemsInCurrentPage: layersResponse.data.length,
      hasMorePages: layersResponse.skip + layersResponse.limit < layersResponse.total
    });

    // Test domains pagination with metadata
    const domainsResponse: PaginatedResponse<DomainOut> = await domainService.listPageWithMetadata({
      skip: 0,
      limit: 10,
      sort: 'title'
    });

    console.log('Domains pagination response:', {
      totalItems: domainsResponse.total,
      currentPage: domainsResponse.skip / domainsResponse.limit + 1,
      itemsPerPage: domainsResponse.limit,
      itemsInCurrentPage: domainsResponse.data.length,
      hasMorePages: domainsResponse.skip + domainsResponse.limit < domainsResponse.total
    });

    // Test terms pagination with metadata
    const termsResponse: PaginatedResponse<TermOut> = await termService.listPageWithMetadata({
      skip: 0,
      limit: 10,
      sort: 'title'
    });

    console.log('Terms pagination response:', {
      totalItems: termsResponse.total,
      currentPage: termsResponse.skip / termsResponse.limit + 1,
      itemsPerPage: termsResponse.limit,
      itemsInCurrentPage: termsResponse.data.length,
      hasMorePages: termsResponse.skip + termsResponse.limit < termsResponse.total
    });

    return {
      layers: layersResponse,
      domains: domainsResponse,
      terms: termsResponse
    };
  } catch (error) {
    console.error('Error testing pagination features:', error);
    throw error;
  }
}

// Helper function to calculate pagination metadata
export function calculatePaginationInfo<T>(response: PaginatedResponse<T>) {
  const currentPage = Math.floor(response.skip / response.limit) + 1;
  const totalPages = Math.ceil(response.total / response.limit);
  const hasNextPage = currentPage < totalPages;
  const hasPreviousPage = currentPage > 1;

  return {
    currentPage,
    totalPages,
    hasNextPage,
    hasPreviousPage,
    startItem: response.skip + 1,
    endItem: Math.min(response.skip + response.limit, response.total),
    totalItems: response.total,
    itemsInCurrentPage: response.data.length
  };
}

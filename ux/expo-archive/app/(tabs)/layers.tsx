/**
 * Layers Page
 * 
 * Page for viewing and editing layers using the LayerTable component
 */

import React from 'react';
import { VStack } from '../../components/ui/vstack';
import { HStack } from '../../components/ui/hstack';
import { Text } from '../../components/ui/text';
import { Button, ButtonText } from '../../components/ui/button';
import { LayerTable } from '../../components/common';
import { useCreateLayer } from '../../api/hooks/layers';
import { handleApiError } from '../../api/errors/errorHandlers';
import type { components } from '../../api/client/types';

type LayerCreate = components['schemas']['LayerCreate'];

export default function LayersPage() {
  const createLayer = useCreateLayer();

  const handleCreateLayer = async () => {
    try {
      const newLayer: LayerCreate = {
        title: 'New Layer',
        definition: 'A new layer for organizing domains and terms',
        primary_predicate: 'contains',
      };

      await createLayer.mutateAsync(newLayer);
      // Success is handled by the mutation onSuccess callback
    } catch (error) {
      handleApiError(error);
    }
  };

  return (
    <VStack className="flex-1 p-4">
      {/* Header */}
      <HStack className="justify-between items-center mb-6">
        <VStack>
          <Text className="text-2xl font-bold">Layers</Text>
          <Text className="text-gray-600">Manage organizational layers</Text>
        </VStack>
        <Button onPress={handleCreateLayer} disabled={createLayer.isPending}>
          <ButtonText>
            {createLayer.isPending ? 'Creating...' : 'Create Layer'}
          </ButtonText>
        </Button>
      </HStack>

      {/* Table */}
      <LayerTable
        showActions={true}
        enableInlineEdit={true}
        enableSearch={true}
        enablePagination={true}
        pageSize={20}
      />
    </VStack>
  );
}

/**
 * Domains Page
 * 
 * Page for viewing and editing domains using the DomainTable component
 */

import React, { useState } from 'react';
import { VStack } from '../../components/ui/vstack';
import { HStack } from '../../components/ui/hstack';
import { Text } from '../../components/ui/text';
import { Button, ButtonText } from '../../components/ui/button';
import { Select, SelectTrigger, SelectInput, SelectContent, SelectItem } from '../../components/ui/select';
import { DomainTable } from '../../components/common';
import { useCreateDomain } from '../../api/hooks/domains';
import { useLayers } from '../../api/hooks/layers';
import { handleApiError } from '../../api/errors/errorHandlers';
import type { components } from '../../api/client/types';

type DomainCreate = components['schemas']['DomainCreate'];

export default function DomainsPage() {
  const [selectedLayerId, setSelectedLayerId] = useState<string>('');
  const createDomain = useCreateDomain();
  const { data: layers } = useLayers();

  const handleCreateDomain = async () => {
    if (!selectedLayerId) {
      handleApiError(new Error('Please select a layer first'));
      return;
    }

    try {
      const newDomain: DomainCreate = {
        title: 'New Domain',
        definition: 'A new domain within the selected layer',
        layer_id: selectedLayerId,
      };

      await createDomain.mutateAsync(newDomain);
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
          <Text className="text-2xl font-bold">Domains</Text>
          <Text className="text-gray-600">Manage domains within layers</Text>
        </VStack>
        <Button onPress={handleCreateDomain} disabled={createDomain.isPending || !selectedLayerId}>
          <ButtonText>
            {createDomain.isPending ? 'Creating...' : 'Create Domain'}
          </ButtonText>
        </Button>
      </HStack>

      {/* Filter Controls */}
      <HStack className="mb-4" space="md">
        <Text className="self-center">Filter by Layer:</Text>
        <Select
          selectedValue={selectedLayerId}
          onValueChange={setSelectedLayerId}
        >
          <SelectTrigger className="flex-1">
            <SelectInput placeholder="Select a layer (optional)" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="" label="All layers" />
            {layers?.map((layer) => (
              <SelectItem 
                key={layer.id} 
                value={layer.id} 
                label={layer.title}
              />
            ))}
          </SelectContent>
        </Select>
      </HStack>

      {/* Table */}
      <DomainTable
        layerId={selectedLayerId || undefined}
        showActions={true}
        enableInlineEdit={true}
        enableSearch={true}
        enablePagination={true}
        pageSize={20}
      />
    </VStack>
  );
}

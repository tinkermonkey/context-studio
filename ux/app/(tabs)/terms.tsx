/**
 * Terms Page
 * 
 * Page for viewing and editing terms using the TermTable component
 */

import React, { useState } from 'react';
import { VStack } from '../../components/ui/vstack';
import { HStack } from '../../components/ui/hstack';
import { Text } from '../../components/ui/text';
import { Button, ButtonText } from '../../components/ui/button';
import { Select, SelectTrigger, SelectInput, SelectContent, SelectItem } from '../../components/ui/select';
import { TermTable } from '../../components/common';
import { useCreateTerm } from '../../api/hooks/terms';
import { useLayers } from '../../api/hooks/layers';
import { useDomains } from '../../api/hooks/domains';
import { handleApiError } from '../../api/errors/errorHandlers';
import type { components } from '../../api/client/types';

type TermCreate = components['schemas']['TermCreate'];

export default function TermsPage() {
  const [selectedLayerId, setSelectedLayerId] = useState<string>('');
  const [selectedDomainId, setSelectedDomainId] = useState<string>('');
  const createTerm = useCreateTerm();
  const { data: layers } = useLayers();
  const { data: domains } = useDomains(
    selectedLayerId ? { layer_id: selectedLayerId } : undefined
  );

  const handleCreateTerm = async () => {
    if (!selectedDomainId) {
      handleApiError(new Error('Please select a domain first'));
      return;
    }

    try {
      const newTerm: TermCreate = {
        title: 'New Term',
        definition: 'A new term within the selected domain',
        domain_id: selectedDomainId,
        layer_id: selectedLayerId || (domains?.find(d => d.id === selectedDomainId)?.layer_id || ''),
      };

      await createTerm.mutateAsync(newTerm);
      // Success is handled by the mutation onSuccess callback
    } catch (error) {
      handleApiError(error);
    }
  };

  // Reset domain selection when layer changes
  const handleLayerChange = (layerId: string) => {
    setSelectedLayerId(layerId);
    setSelectedDomainId(''); // Reset domain when layer changes
  };

  return (
    <VStack className="flex-1 p-4">
      {/* Header */}
      <HStack className="justify-between items-center mb-6">
        <VStack>
          <Text className="text-2xl font-bold">Terms</Text>
          <Text className="text-gray-600">Manage terms within domains</Text>
        </VStack>
        <Button onPress={handleCreateTerm} disabled={createTerm.isPending || !selectedDomainId}>
          <ButtonText>
            {createTerm.isPending ? 'Creating...' : 'Create Term'}
          </ButtonText>
        </Button>
      </HStack>

      {/* Filter Controls */}
      <VStack className="mb-4" space="md">
        <HStack space="md">
          <Text className="self-center">Filter by Layer:</Text>
          <Select
            selectedValue={selectedLayerId}
            onValueChange={handleLayerChange}
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

        <HStack space="md">
          <Text className="self-center">Filter by Domain:</Text>
          <Select
            selectedValue={selectedDomainId}
            onValueChange={setSelectedDomainId}
          >
            <SelectTrigger className="flex-1">
              <SelectInput placeholder="Select a domain (optional)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="" label="All domains" />
              {domains?.map((domain) => (
                <SelectItem 
                  key={domain.id} 
                  value={domain.id} 
                  label={domain.title}
                />
              ))}
            </SelectContent>
          </Select>
        </HStack>
      </VStack>

      {/* Table */}
      <TermTable
        layerId={selectedLayerId || undefined}
        domainId={selectedDomainId || undefined}
        showActions={true}
        enableInlineEdit={true}
        enableSearch={true}
        enablePagination={true}
        pageSize={20}
      />
    </VStack>
  );
}

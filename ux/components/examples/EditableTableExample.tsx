/**
 * EditableTableExample Component
 *
 * Example component demonstrating how to use the editable table components
 */

import React, { useState } from 'react';
import { VStack } from '../ui/vstack';
import { HStack } from '../ui/hstack';
import { Button, ButtonText } from '../ui/button';
import { Text } from '../ui/text';
import { Select, SelectTrigger, SelectItem, SelectContent, SelectInput } from '../ui/select';
import { LayerTable, DomainTable, TermTable } from '../common';
import type { NodeType } from '../common';

export const EditableTableExample: React.FC = () => {
  const [selectedTable, setSelectedTable] = useState<NodeType>('layer');
  const [selectedLayerId, setSelectedLayerId] = useState<string>('');
  const [selectedDomainId, setSelectedDomainId] = useState<string>('');

  const renderTable = () => {
    switch (selectedTable) {
      case 'layer':
        return (
          <LayerTable
            showActions={true}
            enableInlineEdit={true}
            enableSearch={true}
            enablePagination={true}
            pageSize={10}
          />
        );
      case 'domain':
        return (
          <DomainTable
            layerId={selectedLayerId || undefined}
            showActions={true}
            enableInlineEdit={true}
            enableSearch={true}
            enablePagination={true}
            pageSize={10}
          />
        );
      case 'term':
        return (
          <TermTable
            domainId={selectedDomainId || undefined}
            showActions={true}
            enableInlineEdit={true}
            enableSearch={true}
            enablePagination={true}
            pageSize={10}
          />
        );
      default:
        return null;
    }
  };

  return (
    <VStack className="flex-1 p-4">
      <HStack className="justify-between items-center mb-4" space="md">
        <Text className="text-xl font-bold">Editable Table Examples</Text>
        
        <HStack space="md">
          <Button
            variant={selectedTable === 'layer' ? 'solid' : 'outline'}
            onPress={() => setSelectedTable('layer')}
          >
            <ButtonText>Layers</ButtonText>
          </Button>
          <Button
            variant={selectedTable === 'domain' ? 'solid' : 'outline'}
            onPress={() => setSelectedTable('domain')}
          >
            <ButtonText>Domains</ButtonText>
          </Button>
          <Button
            variant={selectedTable === 'term' ? 'solid' : 'outline'}
            onPress={() => setSelectedTable('term')}
          >
            <ButtonText>Terms</ButtonText>
          </Button>
        </HStack>
      </HStack>

      {/* Filter Controls */}
      {selectedTable === 'domain' && (
        <HStack className="mb-4" space="md">
          <Text>Filter by Layer ID:</Text>
          <Select
            selectedValue={selectedLayerId}
            onValueChange={setSelectedLayerId}
          >
            <SelectTrigger>
              <SelectInput placeholder="Select layer (optional)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="" label="All layers" />
              {/* Add actual layer options here */}
            </SelectContent>
          </Select>
        </HStack>
      )}

      {selectedTable === 'term' && (
        <HStack className="mb-4" space="md">
          <Text>Filter by Domain ID:</Text>
          <Select
            selectedValue={selectedDomainId}
            onValueChange={setSelectedDomainId}
          >
            <SelectTrigger>
              <SelectInput placeholder="Select domain (optional)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="" label="All domains" />
              {/* Add actual domain options here */}
            </SelectContent>
          </Select>
        </HStack>
      )}

      {/* Table */}
      <VStack className="flex-1">
        {renderTable()}
      </VStack>
    </VStack>
  );
};

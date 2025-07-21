import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LayerList } from '../../components/examples/LayerList';
import { VStack } from '../../components/ui/vstack';
import { Text } from '../../components/ui/text';

const queryClient = new QueryClient();

const ExploreScreen: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <VStack className="flex-1 bg-white dark:bg-black p-4">
        <Text className="text-2xl font-bold mb-6">Explore Layers</Text>
        <LayerList />
      </VStack>
    </QueryClientProvider>
  );
};

export default ExploreScreen;

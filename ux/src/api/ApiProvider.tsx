/**
 * API Provider Component
 * 
 * React Query provider for the Context Studio API
 */

import React from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './utils/queryClient';

interface ApiProviderProps {
  children: React.ReactNode;
}

export const ApiProvider: React.FC<ApiProviderProps> = ({ children }) => {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

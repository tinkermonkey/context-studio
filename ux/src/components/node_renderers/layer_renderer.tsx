
import React from 'react';
import { useStructureNode } from '@/api/hooks/structure_nodes/useStructureNodes';

type LayerProps = {
  layer_id: string;
};

export const LayerRenderer: React.FC<LayerProps> = ({ layer_id }) => {
  const { data, isLoading, isError } = useStructureNode(layer_id);

  if (isLoading) return <span>Loading...</span>;
  if (isError || !data) return <span>Layer not found</span>;

  return <span>{data.title}</span>;
};

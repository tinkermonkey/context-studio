import React from "react";
import { useOntologyClass } from "@/api/hooks/ontologyClasses";

type LayerProps = {
  layer_id: string;
};

export const LayerRenderer: React.FC<LayerProps> = ({ layer_id }) => {
  const { data, isLoading, isError } = useOntologyClass(layer_id);

  if (isLoading) return <span>Loading...</span>;
  if (isError || !data) return <span>Layer not found</span>;

  return <span>{data.title}</span>;
};

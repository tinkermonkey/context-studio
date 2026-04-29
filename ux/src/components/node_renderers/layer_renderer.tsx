import React from "react";
import { useClass } from "@/api/hooks/ontologyClasses";

type LayerProps = {
  layer_id: string;
};

export const LayerRenderer: React.FC<LayerProps> = ({ layer_id }) => {
  const { data, isLoading, isError } = useClass(layer_id);

  if (isLoading) return <span>Loading...</span>;
  if (isError || !data) return <span>Layer not found</span>;

  return <span>{data.title}</span>;
};

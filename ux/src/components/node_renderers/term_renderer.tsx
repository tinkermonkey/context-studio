import React from "react";
import { useStructureNode } from "@/api/hooks/structure_nodes/useStructureNodes";

type TermProps = {
  term_id: string;
};

export const TermRenderer: React.FC<TermProps> = ({ term_id }) => {
  const { data, isLoading, isError } = useStructureNode(term_id);

  if (isLoading) return <span>Loading...</span>;
  if (isError || !data) return <span>Term not found</span>;

  return <span>{data.title}</span>;
};

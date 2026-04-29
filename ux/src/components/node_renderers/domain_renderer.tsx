import React from "react";
import { useClass } from "@/api/hooks/ontologyClasses";

type DomainProps = {
  domain_id: string;
};

export const DomainRenderer: React.FC<DomainProps> = ({ domain_id }) => {
  const { data, isLoading, isError } = useClass(domain_id);

  if (isLoading) return <span>Loading...</span>;
  if (isError || !data) return <span>Domain not found</span>;

  return <span>{data.title}</span>;
};

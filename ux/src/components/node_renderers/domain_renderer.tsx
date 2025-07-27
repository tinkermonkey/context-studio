
import React from 'react';
import { useDomain } from '@/api/hooks/domains/useDomains';

type DomainProps = {
  domain_id: string;
};

export const DomainRenderer: React.FC<DomainProps> = ({ domain_id }) => {
  const { data, isLoading, isError } = useDomain(domain_id);

  if (isLoading) return <span>Loading...</span>;
  if (isError || !data) return <span>Domain not found</span>;

  return <span>{data.title}</span>;
};

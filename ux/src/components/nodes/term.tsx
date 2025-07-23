
import React from 'react';
import { useTerm } from '@/api/hooks/terms/useTerms';

type TermProps = {
  term_id: string;
};

export const Term: React.FC<TermProps> = ({ term_id }) => {
  const { data, isLoading, isError } = useTerm(term_id);

  if (isLoading) return <span>Loading...</span>;
  if (isError || !data) return <span>Term not found</span>;

  return <span>{data.title}</span>;
};

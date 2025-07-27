import React from 'react';
import { Badge } from 'flowbite-react';
import type { components } from '@/api/client/types';

type TermRelationshipOut = components['schemas']['TermRelationshipOut'];

interface RelationshipTermsDisplayProps {
  relationships: TermRelationshipOut[];
  currentTermId: string;
  direction: 'outgoing' | 'incoming';
  color: 'blue' | 'green';
}

export const RelationshipTermsDisplay: React.FC<RelationshipTermsDisplayProps> = ({
  relationships,
  currentTermId,
  direction,
  color
}) => {
  return (
    <div className="flex flex-wrap gap-2">
      {relationships.map((rel) => {
        const termId = direction === 'outgoing' ? rel.target_term_id : rel.source_term_id;
        return (
          <Badge key={rel.id} color={color} className="cursor-pointer">
            {termId}
          </Badge>
        );
      })}
    </div>
  );
};

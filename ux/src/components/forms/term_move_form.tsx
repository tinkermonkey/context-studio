/**
 * Term Move Form
 * 
 * Form for moving terms between domains
 */

import React, { useState } from 'react';
import { Button, Label, Checkbox } from 'flowbite-react';
import { TermOut } from '@/api/services/terms';
import { DomainSelector } from '@/components/node_selectors/domain_selector';
import { useMoveTerms } from '@/api/hooks/terms';

interface TermMoveFormProps {
  selectedNodes: TermOut[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function TermMoveForm({ selectedNodes, onSuccess, onCancel }: TermMoveFormProps) {
  const [targetDomainId, setTargetDomainId] = useState<string>('');
  const [moveChildren, setMoveChildren] = useState(true);
  const moveTerms = useMoveTerms();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!targetDomainId) {
      return;
    }

    try {
      await moveTerms.mutateAsync({
        term_ids: selectedNodes.map(term => term.id),
        target_domain_id: targetDomainId,
        move_children: moveChildren,
      });
      
      onSuccess();
    } catch (error) {
      console.error('Failed to move terms:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 z-10">
      <div>
        <Label htmlFor="target-domain">Target Domain</Label>
        <DomainSelector
          value={targetDomainId}
          onSelect={(domain) => setTargetDomainId(domain?.id || '')}
          className='z-10'
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="move-children"
          checked={moveChildren}
          onChange={(e) => setMoveChildren(e.target.checked)}
        />
        <Label htmlFor="move-children" className="text-sm">
          Also move all child terms recursively
        </Label>
      </div>

      <div className="text-sm text-gray-600">
        Moving {selectedNodes.length} term{selectedNodes.length > 1 ? 's' : ''} to a new domain.
        {moveChildren && ' All child terms will also be moved recursively.'}
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button
          type="button"
          color="gray"
          onClick={onCancel}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          color="blue"
          disabled={!targetDomainId || moveTerms.isPending}
        >
          {moveTerms.isPending ? 'Moving...' : 'Move Terms'}
        </Button>
      </div>
    </form>
  );
}

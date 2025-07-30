/**
 * Domain Move Form
 * 
 * Form for moving domains between layers
 */

import React, { useState } from 'react';
import { Button, Label, Checkbox } from 'flowbite-react';
import { DomainOut } from '@/api/services/domains';
import { LayerSelector } from '@/components/node_selectors/layer_selector';
import { useMoveDomains } from '@/api/hooks/domains';

interface DomainMoveFormProps {
  selectedNodes: DomainOut[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function DomainMoveForm({ selectedNodes, onSuccess, onCancel }: DomainMoveFormProps) {
  const [targetLayerId, setTargetLayerId] = useState<string>('');
  const [moveTerms, setMoveTerms] = useState(true);
  const moveDomains = useMoveDomains();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!targetLayerId) {
      return;
    }

    try {
      await moveDomains.mutateAsync({
        domain_ids: selectedNodes.map(domain => domain.id),
        target_layer_id: targetLayerId,
        move_terms: moveTerms,
      });
      
      onSuccess();
    } catch (error) {
      console.error('Failed to move domains:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="target-layer">Target Layer</Label>
        <LayerSelector
          value={targetLayerId}
          onSelect={(layer) => setTargetLayerId(layer?.id || '')}
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="move-terms"
          checked={moveTerms}
          onChange={(e) => setMoveTerms(e.target.checked)}
        />
        <Label htmlFor="move-terms" className="text-sm">
          Also move all terms contained in these domains
        </Label>
      </div>

      <div className="text-sm text-gray-600">
        Moving {selectedNodes.length} domain{selectedNodes.length > 1 ? 's' : ''} to a new layer.
        {moveTerms && ' All terms in these domains will also be moved.'}
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
          disabled={!targetLayerId || moveDomains.isPending}
        >
          {moveDomains.isPending ? 'Moving...' : 'Move Domains'}
        </Button>
      </div>
    </form>
  );
}

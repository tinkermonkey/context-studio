/**
 * Example Domain Form Component
 * 
 * Demonstrates enhanced error handling with validation
 */

import React, { useState } from 'react';
import { Button, Label, TextInput, Textarea, Alert } from 'flowbite-react';
import { useCreateDomainWithFormErrors } from '../../api/hooks/domains/useDomainMutations';
import { InlineApiError } from '../misc/error_boundary';
import type { components } from '../../api/client/types';

type DomainCreate = components['schemas']['DomainCreate'];

interface DomainFormProps {
  onSuccess?: (domain: components['schemas']['DomainOut']) => void;
  onCancel?: () => void;
}

export const DomainForm: React.FC<DomainFormProps> = ({ onSuccess, onCancel }) => {
  const [formData, setFormData] = useState<DomainCreate>({
    title: '',
    definition: '',
    layer_id: ''
  });

  const { mutate, isPending, formError, isValidationError } = useCreateDomainWithFormErrors();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    mutate(formData, {
      onSuccess: (data) => {
        setFormData({ title: '', definition: '', layer_id: '' });
        onSuccess?.(data);
      }
    });
  };

  const handleChange = (field: keyof DomainCreate) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFormData(prev => ({ ...prev, [field]: e.target.value }));
  };

  // Get field-specific validation errors
  const getFieldErrorsLocal = (fieldErrors: Record<string, string[]> | undefined, field: string): string[] => {
    return fieldErrors?.[field] || [];
  };

  const titleErrors = getFieldErrorsLocal(formError?.fieldErrors, 'title');
  const definitionErrors = getFieldErrorsLocal(formError?.fieldErrors, 'definition');
  const layerIdErrors = getFieldErrorsLocal(formError?.fieldErrors, 'layer_id');

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Create New Domain</h2>
      
      {/* Display general error if not validation error */}
      {formError && !isValidationError && (
        <Alert color="failure">
          {formError.message}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <Label htmlFor="title">Title</Label>
          <TextInput
            id="title"
            value={formData.title}
            onChange={handleChange('title')}
            color={titleErrors.length > 0 ? 'failure' : undefined}
            required
          />
          {titleErrors.length > 0 && (
            <p className="text-red-600 text-sm mt-1">{titleErrors.join(', ')}</p>
          )}
        </div>

        <div>
          <Label htmlFor="definition">Definition</Label>
          <Textarea
            id="definition"
            value={formData.definition || ''}
            onChange={handleChange('definition')}
            rows={3}
            color={definitionErrors.length > 0 ? 'failure' : undefined}
          />
          {definitionErrors.length > 0 && (
            <p className="text-red-600 text-sm mt-1">{definitionErrors.join(', ')}</p>
          )}
        </div>

        <div>
          <Label htmlFor="layer_id">Layer ID</Label>
          <TextInput
            id="layer_id"
            value={formData.layer_id || ''}
            onChange={handleChange('layer_id')}
            color={layerIdErrors.length > 0 ? 'failure' : undefined}
          />
          {layerIdErrors.length > 0 && (
            <p className="text-red-600 text-sm mt-1">{layerIdErrors.join(', ')}</p>
          )}
        </div>

        {/* Display validation errors inline */}
        {isValidationError && (
          <InlineApiError 
            error={formError} 
            className="mt-2"
          />
        )}

        <div className="flex space-x-2">
          <Button 
            type="submit" 
            disabled={isPending}
          >
            {isPending ? 'Creating...' : 'Create Domain'}
          </Button>
          
          {onCancel && (
            <Button 
              type="button" 
              color="gray" 
              onClick={onCancel}
              disabled={isPending}
            >
              Cancel
            </Button>
          )}
        </div>
      </form>
    </div>
  );
};

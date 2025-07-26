import React from "react";
import { 
  Select, 
  TextInput, 
  Button,
  Card,
  Accordion,
  AccordionContent,
  AccordionPanel,
  AccordionTitle,
  Label
} from "flowbite-react";
import { Filter, X } from "lucide-react";

export interface QueryFilter {
  field: string;
  operator: 'equals' | 'contains' | 'starts_with' | 'ends_with' | 'gt' | 'gte' | 'lt' | 'lte' | 'between' | 'in';
  value: string | number | (string | number)[];
  label?: string;
}

export interface FieldDefinition {
  field: string;
  label: string;
  type: 'text' | 'number' | 'date' | 'select';
  operators?: QueryFilter['operator'][];
  options?: { value: string | number; label: string }[]; // For select fields
}

interface QueryFiltersProps {
  /** Field definitions for the filterable fields */
  fields: FieldDefinition[];
  /** Current filter values */
  filters: QueryFilter[];
  /** Callback when filters change */
  onFiltersChange: (filters: QueryFilter[]) => void;
  /** Whether to show the filters panel initially collapsed */
  defaultCollapsed?: boolean;
  /** Custom title for the filters section */
  title?: string;
}

const DEFAULT_OPERATORS_BY_TYPE: Record<FieldDefinition['type'], QueryFilter['operator'][]> = {
  text: ['equals', 'contains', 'starts_with', 'ends_with'],
  number: ['equals', 'gt', 'gte', 'lt', 'lte', 'between'],
  date: ['equals', 'gt', 'gte', 'lt', 'lte', 'between'],
  select: ['equals', 'in'],
};

const OPERATOR_LABELS: Record<QueryFilter['operator'], string> = {
  equals: 'Equals',
  contains: 'Contains',
  starts_with: 'Starts with',
  ends_with: 'Ends with',
  gt: 'Greater than',
  gte: 'Greater than or equal',
  lt: 'Less than',
  lte: 'Less than or equal',
  between: 'Between',
  in: 'In list',
};

const QueryFilters: React.FC<QueryFiltersProps> = ({
  fields,
  filters,
  onFiltersChange,
  defaultCollapsed = true,
  title = "Advanced Filters",
}) => {
  const addFilter = () => {
    const firstField = fields[0];
    if (!firstField) return;

    const availableOperators = firstField.operators || DEFAULT_OPERATORS_BY_TYPE[firstField.type];
    const newFilter: QueryFilter = {
      field: firstField.field,
      operator: availableOperators[0],
      value: '',
      label: firstField.label,
    };
    
    onFiltersChange([...filters, newFilter]);
  };

  const updateFilter = (index: number, updates: Partial<QueryFilter>) => {
    const newFilters = [...filters];
    newFilters[index] = { ...newFilters[index], ...updates };
    onFiltersChange(newFilters);
  };

  const removeFilter = (index: number) => {
    const newFilters = filters.filter((_, i) => i !== index);
    onFiltersChange(newFilters);
  };

  const clearAllFilters = () => {
    onFiltersChange([]);
  };

  const getFieldDefinition = (fieldName: string): FieldDefinition | undefined => {
    return fields.find(f => f.field === fieldName);
  };

  const renderValueInput = (filter: QueryFilter, index: number) => {
    const fieldDef = getFieldDefinition(filter.field);
    if (!fieldDef) return null;

    if (fieldDef.type === 'select' && fieldDef.options) {
      return (
        <Select
          value={filter.value as string}
          onChange={(e) => updateFilter(index, { value: e.target.value })}
          className="min-w-[120px]"
        >
          <option value="">Select...</option>
          {fieldDef.options.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      );
    }

    if (filter.operator === 'between') {
      const values = Array.isArray(filter.value) ? filter.value : ['', ''];
      return (
        <div className="flex gap-2 items-center">
          <TextInput
            type={fieldDef.type === 'number' ? 'number' : fieldDef.type === 'date' ? 'date' : 'text'}
            placeholder="From"
            value={values[0] || ''}
            onChange={(e) => updateFilter(index, { value: [e.target.value, values[1] || ''] })}
            className="min-w-[100px]"
          />
          <span className="text-gray-500">to</span>
          <TextInput
            type={fieldDef.type === 'number' ? 'number' : fieldDef.type === 'date' ? 'date' : 'text'}
            placeholder="To"
            value={values[1] || ''}
            onChange={(e) => updateFilter(index, { value: [values[0] || '', e.target.value] })}
            className="min-w-[100px]"
          />
        </div>
      );
    }

    if (filter.operator === 'in') {
      return (
        <TextInput
          placeholder="Comma-separated values"
          value={Array.isArray(filter.value) ? filter.value.join(', ') : filter.value}
          onChange={(e) => {
            const values = e.target.value.split(',').map(v => v.trim()).filter(v => v);
            updateFilter(index, { value: values });
          }}
          className="min-w-[150px]"
        />
      );
    }

    return (
      <TextInput
        type={fieldDef.type === 'number' ? 'number' : fieldDef.type === 'date' ? 'date' : 'text'}
        placeholder="Value"
        value={filter.value as string}
        onChange={(e) => updateFilter(index, { value: e.target.value })}
        className="min-w-[120px]"
      />
    );
  };

  if (fields.length === 0) {
    return null;
  }

  return (
    <Accordion collapseAll={defaultCollapsed} className="mb-4">
      <AccordionPanel>
        <AccordionTitle className="flex items-center gap-2">
          <Filter size={16} className="inline mr-2"/>
          {title}
          {filters.length > 0 && (
            <span className="bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs font-medium px-2 py-1 rounded-full">
              {filters.length}
            </span>
          )}
        </AccordionTitle>
        <AccordionContent>
          <div className="space-y-3">
            {filters.map((filter, index) => {
              const fieldDef = getFieldDefinition(filter.field);
              const availableOperators = fieldDef?.operators || DEFAULT_OPERATORS_BY_TYPE[fieldDef?.type || 'text'];
              
              return (
                <Card key={index} className="p-3">
                  <div className="flex flex-wrap items-center gap-3">
                    {/* Field Selection */}
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Field</Label>
                      <Select
                        value={filter.field}
                        onChange={(e) => {
                          const newFieldDef = getFieldDefinition(e.target.value);
                          const newOperators = newFieldDef?.operators || DEFAULT_OPERATORS_BY_TYPE[newFieldDef?.type || 'text'];
                          updateFilter(index, { 
                            field: e.target.value,
                            operator: newOperators[0],
                            value: '',
                            label: newFieldDef?.label 
                          });
                        }}
                        className="min-w-[120px]"
                      >
                        {fields.map(field => (
                          <option key={field.field} value={field.field}>
                            {field.label}
                          </option>
                        ))}
                      </Select>
                    </div>

                    {/* Operator Selection */}
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Condition</Label>
                      <Select
                        value={filter.operator}
                        onChange={(e) => updateFilter(index, { 
                          operator: e.target.value as QueryFilter['operator'],
                          value: '' // Reset value when operator changes
                        })}
                        className="min-w-[140px]"
                      >
                        {availableOperators.map(op => (
                          <option key={op} value={op}>
                            {OPERATOR_LABELS[op]}
                          </option>
                        ))}
                      </Select>
                    </div>

                    {/* Value Input */}
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Value</Label>
                      {renderValueInput(filter, index)}
                    </div>

                    {/* Remove Button */}
                    <Button
                      color="gray"
                      size="sm"
                      onClick={() => removeFilter(index)}
                      className="mt-5"
                    >
                      <X size={14} />
                    </Button>
                  </div>
                </Card>
              );
            })}

            {/* Action Buttons */}
            <div className="flex gap-2 pt-2">
              <Button
                color="blue"
                size="sm"
                onClick={addFilter}
              >
                Add Filter
              </Button>
              {filters.length > 0 && (
                <Button
                  color="gray"
                  size="sm"
                  onClick={clearAllFilters}
                >
                  Clear All
                </Button>
              )}
            </div>
          </div>
        </AccordionContent>
      </AccordionPanel>
    </Accordion>
  );
};

export { QueryFilters };

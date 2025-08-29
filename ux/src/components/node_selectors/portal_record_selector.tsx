import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactDOM from 'react-dom';
import { Button, Badge, TextInput, Spinner, Checkbox, Label } from 'flowbite-react';
import { ChevronDown, Search, X, CircleX } from 'lucide-react';
import SearchHighlight from '@/components/misc/search_highlight';

export interface FieldMap<T = any> {
  value: keyof T | string;
  title: keyof T | string;
  definition?: keyof T | string;
}

export interface PortalRecordSelectorProps<T = any> {
  records: T[];
  loading?: boolean;
  error?: string | null;
  fieldMap: FieldMap<T>;
  placeholder?: string;
  disabled?: boolean;
  multi?: boolean;
  value?: string | string[];
  onSelect?: (record?: T) => void; // single select
  onSelectionChange?: (ids: string[]) => void; // multi select
  maxSelections?: number;
}

export function PortalRecordSelector<T = any>(props: PortalRecordSelectorProps<T>): React.ReactElement {
  const {
    records,
    loading = false,
    error = null,
    fieldMap,
    placeholder = 'Select Record',
    disabled = false,
    multi = false,
    value,
    onSelect,
    onSelectionChange,
    maxSelections,
  } = props;

  const [searchTerm, setSearchTerm] = useState('');
  const [showDefinitions, setShowDefinitions] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const optionRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});

  const getValue = (item: any) => String(item[fieldMap.value as string] ?? '');
  const getTitle = (item: any) => String(item[fieldMap.title as string] ?? '');
  const getDefinition = (item: any) =>
    fieldMap.definition ? String(item[fieldMap.definition as string] ?? '') : '';

  const filtered = useMemo(() => {
    if (!records) return [] as T[];
    const q = searchTerm.trim().toLowerCase();
    if (!q) return records;
    return records.filter((r) => {
      const title = getTitle(r).toLowerCase();
      const def = getDefinition(r).toLowerCase();
      const id = getValue(r).toLowerCase();
      // include definition matches only if showDefinitions is enabled
      return title.includes(q) || id.includes(q) || (showDefinitions && def.includes(q));
    });
  }, [records, searchTerm, showDefinitions]);

  // helpers for selection
  const isSelected = (id: string) => {
    if (multi) {
      return Array.isArray(value) && value.includes(id);
    }
    return typeof value === 'string' && value === id;
  };

  const toggleMulti = (id: string) => {
    const current = Array.isArray(value) ? [...value] : [];
    const exists = current.includes(id);
    const next = exists ? current.filter((v) => v !== id) : [...current, id];
    if (maxSelections && next.length > maxSelections) return;
    onSelectionChange?.(next);
  };

  const handleSingleSelect = (item: T) => {
    onSelect?.(item);
    setIsOpen(false);
  };

  // position & outside click + keyboard handling
  useEffect(() => {
    const updatePosition = () => {
      if (!triggerRef.current) return;
      const rect = triggerRef.current.getBoundingClientRect();
      setMenuStyle({
        position: 'absolute',
        top: rect.bottom + window.scrollY,
        left: rect.left + window.scrollX,
        minWidth: rect.width,
        zIndex: 99999,
      });
    };

    const onDocClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        isOpen &&
        menuRef.current &&
        triggerRef.current &&
        !menuRef.current.contains(target) &&
        !triggerRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    };

    const onKey = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        setIsOpen(false);
        triggerRef.current?.focus();
        return;
      }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const ids = filtered.map((r) => getValue(r));
        if (ids.length === 0) return;
        const currentIndex = highlightedId ? ids.indexOf(highlightedId) : -1;
        const nextIndex = e.key === 'ArrowDown' ? Math.min(ids.length - 1, currentIndex + 1) : Math.max(0, currentIndex - 1);
        const nextId = ids[nextIndex];
        setHighlightedId(nextId);
        setTimeout(() => optionRefs.current[nextId]?.focus(), 0);
        return;
      }
      if (e.key === 'Enter') {
        if (highlightedId) {
          const item = records.find((r) => getValue(r) === highlightedId);
          if (item) {
            if (multi) toggleMulti(highlightedId);
            else handleSingleSelect(item);
          }
        }
      }
    };

    if (isOpen) {
      updatePosition();
      window.addEventListener('resize', updatePosition);
      window.addEventListener('scroll', updatePosition, true);
      document.addEventListener('mousedown', onDocClick);
      document.addEventListener('keydown', onKey);
    }

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [isOpen, filtered, highlightedId, records]);

  // render trigger label
  const renderTriggerLabel = () => {
    if (multi) {
      const arr = Array.isArray(value) ? value : [];
      if (arr.length === 0) return placeholder;
      return `${arr.length} selected`;
    }
    if (!value) return placeholder;
    const found = records?.find((r) => getValue(r) === value);
    return found ? getTitle(found) : placeholder;
  };

  return (
    <div className="relative">
      <div className="flex items-center gap-0 w-full">
        <Button
          color="light"
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled}
          className="w-full justify-between"
          ref={triggerRef}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
        >
          <span className="truncate">{renderTriggerLabel()}</span>
          <ChevronDown className="h-4 w-4" />
        </Button>

        {/* clear button for single-select */}
        {!multi && value && typeof value === 'string' && (
          <button
            type="button"
            aria-label="Clear selection"
            className="ml-2 rounded p-1 text-gray-500 hover:bg-gray-100"
            onClick={() => onSelect?.(undefined)}
          >
            <CircleX className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* selected pills for multi */}
      {multi && Array.isArray(value) && value.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {value.map((id) => {
            const item = records.find((r) => getValue(r) === id);
            if (!item) return null;
            return (
              <Badge key={id} className="flex items-center gap-1 py-1 px-2">
                {getTitle(item)}
                <X
                  className="h-3 w-3 ml-1 cursor-pointer hover:text-red-500 inline-flex"
                  onClick={() => toggleMulti(id)}
                />
              </Badge>
            );
          })}
        </div>
      )}

      {isOpen && triggerRef.current
        ? ReactDOM.createPortal(
            <div style={menuStyle} ref={menuRef} role="dialog" aria-modal="false">
              <div className="bg-white border rounded-md shadow-lg dark:bg-gray-800 dark:border-gray-700">
                <div className="p-2 border-b dark:border-gray-700">
                  <TextInput
                    placeholder="Search..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    icon={Search}
                    onClick={(e) => e.stopPropagation()}
                    aria-label="Search records"
                  />
                  <div className="flex items-center pt-2">
                    <Checkbox
                      id="portal-record-selector-show-definitions"
                      checked={showDefinitions}
                      onChange={() => setShowDefinitions(!showDefinitions)}
                    />
                    <Label htmlFor="portal-record-selector-show-definitions" className="flex pl-2">
                      Show Definitions
                    </Label>
                  </div>
                </div>

                <div className="max-h-60 overflow-y-auto" role="listbox" aria-label="Records list">
                  {loading ? (
                    <div className="p-4 text-center">
                      <Spinner size="sm" />
                    </div>
                  ) : filtered.length === 0 ? (
                    <div className="p-4 text-center text-gray-500 dark:text-gray-400">No records found</div>
                  ) : (
                    filtered.map((item) => {
                      const id = getValue(item);
                      return (
                        <div
                          key={id}
                          id={`option-${id}`}
                          role="option"
                          aria-selected={isSelected(id)}
                          tabIndex={-1}
                          ref={(el) => { optionRefs.current[id] = el; }}
                          onMouseEnter={() => setHighlightedId(id)}
                          onClick={() => (multi ? toggleMulti(id) : handleSingleSelect(item))}
                          className={`px-3 py-2 cursor-pointer ${highlightedId === id ? 'bg-gray-100 dark:bg-gray-700' : 'hover:bg-gray-50 dark:hover:bg-gray-700'}`}
                        >
                          {showDefinitions && fieldMap.definition ? (
                            <div className="flex flex-row items-start gap-4">
                              <span className="w-1/3 text-left font-medium whitespace-normal">
                                <SearchHighlight content={getTitle(item)} searchText={searchTerm} />
                              </span>
                              <span className="w-2/3 text-left whitespace-normal text-gray-500">
                                <SearchHighlight content={getDefinition(item)} searchText={searchTerm} />
                              </span>
                            </div>
                          ) : (
                            <div className="font-medium whitespace-normal">
                              <SearchHighlight content={getTitle(item)} searchText={searchTerm} />
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

export default PortalRecordSelector;

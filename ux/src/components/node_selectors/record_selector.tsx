import React, { useEffect, useRef, useState } from "react";
import { Checkbox, Label, Spinner } from "flowbite-react";
import ReactDOM from "react-dom";
import { CircleX } from "lucide-react";
import SearchHighlight from "@/components/misc/search_highlight";

interface FieldMap {
  value: string;
  title: string;
  definition?: string;
}

interface RecordSelectorProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  records: any[];
  loading?: boolean;
  error?: string | null;
  fieldMap?: FieldMap;
  onSelect?: (record: any) => void;  // eslint-disable-line @typescript-eslint/no-explicit-any
  value?: string;
  className?: string;
  search?: string;
  onSearchChange?: (search: string) => void;
}

const defaultFieldMap: FieldMap = {
  value: "id",
  title: "title",
  definition: "definition",
};

export const RecordSelector: React.FC<RecordSelectorProps> = ({
  records,
  loading = false,
  error = null,
  fieldMap = defaultFieldMap,
  onSelect,
  value,
  className = "",
  search: externalSearch,
  onSearchChange,
}) => {
  const [showDefinitions, setShowDefinitions] = useState(false);
  const [internalSearch, setInternalSearch] = useState("");
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});

  // Use external search if provided, otherwise use internal state
  const search = externalSearch !== undefined ? externalSearch : internalSearch;
  const setSearch = onSearchChange || setInternalSearch;

  const selectedRecord = value
    ? records.find((r) => r[fieldMap.value] === value)
    : undefined;
  // Portal-based dropdown to avoid being clipped by parent stacking contexts (modals)
  useEffect(() => {
    const onScrollOrResize = () => {
      if (!open || !triggerRef.current) return;
      const rect = triggerRef.current.getBoundingClientRect();
      setMenuStyle({
        position: "absolute",
        top: rect.bottom + window.scrollY,
        left: rect.left + window.scrollX,
        minWidth: rect.width,
      });
    };

    if (open) {
      onScrollOrResize();
      window.addEventListener("scroll", onScrollOrResize, true);
      window.addEventListener("resize", onScrollOrResize);
    }

    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open]);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        open &&
        menuRef.current &&
        triggerRef.current &&
        !menuRef.current.contains(target) &&
        !triggerRef.current.contains(target)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  // Focus the search input when dropdown opens
  useEffect(() => {
    if (open && searchInputRef.current) {
      // Small delay to ensure the portal has rendered
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 0);
    }
  }, [open]);

  const toggleOpen = () => {
    setOpen((s) => !s);
  };

  const menu = (
    <div
      ref={menuRef}
      style={{ zIndex: 99999 }}
      className="rounded border bg-white shadow-lg"
      role="menu"
    >
      <div className="p-3">
        {error && <div className="text-red-500">{error}</div>}
        <div className="pb-2">
          <div className="relative">
            <input
              ref={searchInputRef}
              id="record-selector-search"
              className="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2 pr-10 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500"
              placeholder="Search..."
              type="search"
              aria-label="Search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onClick={(e) => e.stopPropagation()}
            />
            {loading && (
              <div className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2">
                <Spinner size="sm" />
              </div>
            )}
          </div>
          <div className="flex items-center pt-2">
            <Checkbox
              id="record-selector-show-definitions"
              checked={showDefinitions}
              onChange={() => setShowDefinitions(!showDefinitions)}
            />
            <Label
              htmlFor="record-selector-show-definitions"
              className="flex pl-2"
            >
              Show Definitions
            </Label>
          </div>
        </div>
      </div>
      <div className="max-h-64 overflow-auto">
        {records
          .filter((record) => {
            // Skip client-side filtering if using external search (server-side filtering)
            if (externalSearch !== undefined) {
              return true;
            }
            // Client-side filtering for internal search
            const title = record[fieldMap.title]?.toLowerCase() || "";
            const def = fieldMap.definition
              ? record[fieldMap.definition]?.toLowerCase() || ""
              : "";
            return (
              title.includes(search.toLowerCase()) ||
              (showDefinitions && def.includes(search.toLowerCase()))
            );
          })
          .map((record) => (
            <div
              key={record[fieldMap.value]}
              onClick={() => {
                onSelect?.(record);
                setOpen(false);
              }}
              className={
                "cursor-pointer px-3 py-2 hover:bg-gray-100 " +
                (showDefinitions ? "flex flex-row items-start gap-4" : "")
              }
            >
              {showDefinitions && fieldMap.definition ? (
                <>
                  <span className="w-1/3 text-left font-medium whitespace-normal">
                    <SearchHighlight
                      content={record[fieldMap.title]}
                      searchText={search}
                    />
                  </span>
                  <span className="w-2/3 text-left whitespace-normal text-gray-500">
                    <SearchHighlight
                      content={record[fieldMap.definition]}
                      searchText={search}
                    />
                  </span>
                </>
              ) : (
                <span className="font-medium whitespace-normal">
                  <SearchHighlight
                    content={record[fieldMap.title]}
                    searchText={search}
                  />
                </span>
              )}
            </div>
          ))}
      </div>
    </div>
  );

  return (
    <div className={`relative w-full ${className}`}>
      <div className="flex items-center gap-0">
        <button
          ref={triggerRef}
          type="button"
          onClick={toggleOpen}
          className="inline-flex w-full items-center justify-between rounded border bg-white px-3 py-2 text-left"
        >
          <span className="truncate">
            {loading
              ? "Loading..."
              : selectedRecord
                ? selectedRecord[fieldMap.title]
                : "Select Record"}
          </span>
          <svg
            className="ml-2 h-4 w-4"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden
          >
            <path
              fillRule="evenodd"
              d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.24a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.08z"
              clipRule="evenodd"
            />
          </svg>
        </button>
        {value && (
          <button
            type="button"
            aria-label="Clear selection"
            className="ml-2 rounded p-1 text-gray-500 hover:bg-gray-100"
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
            onClick={() => onSelect?.(undefined as any)}
          >
            <CircleX className="h-4 w-4" />
          </button>
        )}
      </div>
      {open && triggerRef.current
        ? ReactDOM.createPortal(
            <div style={menuStyle}>{menu}</div>,
            document.body,
          )
        : null}
    </div>
  );
};

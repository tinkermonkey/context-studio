import React, { useEffect, useState } from "react";
import {
  Dropdown,
  DropdownItem,
  DropdownDivider,
  DropdownHeader,
  Checkbox,
  Label,
  TextInput,
  Spinner,
} from "flowbite-react";
import { CircleX, Search } from "lucide-react";
import SearchHighlight from "@/components/misc/search_highlight";

interface FieldMap {
  value: string;
  title: string;
  definition?: string;
}

interface RecordSelectorProps {
  records: any[];
  loading?: boolean;
  error?: string | null;
  fieldMap?: FieldMap;
  onSelect?: (record: any) => void;
  value?: string;
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
}) => {
  const [showDefinitions, setShowDefinitions] = useState(false);
  const [search, setSearch] = useState("");

  const selectedRecord = value
    ? records.find((r) => r[fieldMap.value] === value)
    : undefined;

  return (
    <div className="relative w-full">
      <div className="flex items-center gap-0">
        <Dropdown
          label={
            loading
              ? "Loading..."
              : selectedRecord
                ? selectedRecord[fieldMap.title]
                : "Select Record"
          }
          enableTypeAhead={false}
          dismissOnClick={true}
        >
          {error && (
            <DropdownHeader>
              <span className="text-red-500">{error}</span>
            </DropdownHeader>
          )}
          {loading && (
            <DropdownHeader>
              <span>
                <Spinner />
                Loading records...
              </span>
            </DropdownHeader>
          )}
          {!loading && !error && (
            <DropdownHeader>
              <span className="flex pb-4">
                <TextInput
                  id="record-selector-search"
                  className="flex min-w-48 lg:flex"
                  sizing="sm"
                  placeholder="Search..."
                  type="search"
                  icon={Search}
                  aria-label="Search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
              </span>
              <span className="flex pl-1">
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
              </span>
            </DropdownHeader>
          )}
          <DropdownDivider />
          {records
            .filter((record) => {
              const title = record[fieldMap.title]?.toLowerCase() || "";
              const def = fieldMap.definition
                ? record[fieldMap.definition]?.toLowerCase() || ""
                : "";
              return (
                title.includes(search.toLowerCase()) ||
                showDefinitions && def.includes(search.toLowerCase())
              );
            })
            .map((record) => (
              <DropdownItem
                key={record[fieldMap.value]}
                onClick={() => {
                  onSelect?.(record);
                }}
                className={
                  showDefinitions ? "flex flex-row items-start gap-4" : ""
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
              </DropdownItem>
            ))}
        </Dropdown>
        {value && (
          <button
            type="button"
            aria-label="Clear selection"
            className="ml-2 rounded p-1 text-gray-500 hover:bg-gray-100"
            onClick={() => onSelect?.(undefined as any)}
          >
            <CircleX className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
};

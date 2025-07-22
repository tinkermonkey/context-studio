import React, { useEffect, useState } from "react";
import {
  Dropdown,
  DropdownItem,
  DropdownDivider,
  Checkbox,
  Label,
  TextInput,
} from "flowbite-react";
import { layerService, LayerOut } from "@/api/services/layers";
import { CircleX, Search } from "lucide-react";

interface LayerSelectorProps {
  onSelect?: (layer: LayerOut) => void;
  value?: string;
}

export const LayerSelector: React.FC<LayerSelectorProps> = (props) => {
  const { onSelect, value } = props;
  const [layers, setLayers] = useState<LayerOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDefinitions, setShowDefinitions] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    layerService
      .list()
      .then((data) => {
        if (mounted) {
          setLayers(data);
          setError(null);
        }
      })
      .catch((e) => {
        setError("Failed to load layers");
      })
      .finally(() => {
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const selectedLayer = value ? layers.find((l) => l.id === value) : undefined;

  return (
    <div className="relative w-full">
      <div className="flex items-center gap-0">
        <Dropdown
          label={
            loading
              ? "Loading..."
              : selectedLayer
                ? selectedLayer.title
                : "Select Layer"
          }
          dismissOnClick={true}
        >
          {error && (
            <DropdownItem disabled>
              <span className="text-red-500">{error}</span>
            </DropdownItem>
          )}
          {loading && (
            <DropdownItem disabled>
              <span>Loading layers...</span>
            </DropdownItem>
          )}
          {!loading && !error && (
            <>
              <span className="flex p-2">
                <Checkbox
                  id="layer-selector-show-definitions"
                  checked={showDefinitions}
                  onChange={() => {
                    console.log("Show definitions toggled", showDefinitions);
                    setShowDefinitions(!showDefinitions);
                  }}
                />
                <Label
                  htmlFor="layer-selector-show-definitions"
                  className="flex pl-2"
                >
                  Show Definitions
                </Label>
              </span>
              <span className="flex p-2">
                <TextInput
                  id="layer-selector-search"
                  className="flex min-w-64 lg:flex"
                  placeholder="Search..."
                  type="search"
                  icon={Search}
                  aria-label="Search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
              </span>
            </>
          )}
          <DropdownDivider />
          {layers
            .filter(
              (layer) =>
                layer.title.toLowerCase().includes(search.toLowerCase()) ||
                layer.definition?.toLowerCase().includes(search.toLowerCase())
            )
            .map((layer) => (
            <DropdownItem
              key={layer.id}
              onClick={() => {
                onSelect?.(layer);
              }}
              className={
                showDefinitions ? "flex flex-row items-start gap-4" : ""
              }
            >
              {showDefinitions ? (
                <>
                  <span className="w-1/3 text-left font-medium whitespace-normal">
                    {layer.title}
                  </span>
                  <span className="w-2/3 text-left whitespace-normal text-gray-500">
                    {layer.definition}
                  </span>
                </>
              ) : (
                <span className="font-medium whitespace-normal">
                  {layer.title}
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

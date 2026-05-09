import { ReactNode, useState } from "react";
import { ColumnDef } from "@tanstack/react-table";

interface SchemaPageLayoutProps<T extends { id: string }> {
  columns: ColumnDef<T>[];
  data: T[];
  isLoading?: boolean;
  onSelectEntity: (id: string) => void;
  onCloseDrawer: () => void;
  selectedId?: string;
  renderDrawerContent?: (entity: T) => ReactNode;
  children?: ReactNode;
}

export function SchemaPageLayout<T extends { id: string }>({
  columns,
  data,
  isLoading,
  onSelectEntity,
  onCloseDrawer,
  selectedId,
  renderDrawerContent,
  children,
}: SchemaPageLayoutProps<T>) {
  const selectedEntity = data.find((item) => item.id === selectedId);

  return (
    <div className="split-2" data-testid="schema-page-layout">
      <div className="table-area">
        {children}
      </div>
      {selectedEntity && renderDrawerContent && (
        <div data-testid="schema-drawer-container">
          {renderDrawerContent(selectedEntity)}
        </div>
      )}
    </div>
  );
}

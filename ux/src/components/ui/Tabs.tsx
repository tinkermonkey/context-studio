import type { ReactNode } from "react";
import { TabBar as HeimdallTabBar } from "@tinkermonkey/heimdall-ui";

interface Tab {
  id: string;
  label: ReactNode;
  count?: number;
}

interface TabsProps {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}

export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <HeimdallTabBar
      tabs={tabs}
      activeTabId={active}
      onSelectTab={onChange}
      className={className}
    />
  );
}

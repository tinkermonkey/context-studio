import { ReactNode } from "react";

interface Tab {
  id: string;
  label: ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}

export function Tabs({ tabs, active, onChange, className = "" }: TabsProps) {
  const classes = ["tabs", className].filter(Boolean).join(" ");

  return (
    <div className={classes} role="tablist">
      {tabs.map((tab, index) => (
        <button
          key={tab.id}
          id={`tab-${tab.id}`}
          role="tab"
          type="button"
          aria-selected={active === tab.id}
          aria-controls={`panel-${tab.id}`}
          className={`tab ${active === tab.id ? "active" : ""}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

Tabs.displayName = "Tabs";

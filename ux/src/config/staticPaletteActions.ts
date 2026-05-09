import type { PaletteAction } from "@/stores/commandPalette";
import type { NavigateOptions } from "@tanstack/react-router";

type NavigateFunction = (options: NavigateOptions) => Promise<void>;

export function createStaticPaletteActions(navigate: NavigateFunction): PaletteAction[] {
  return [
    {
      id: "open-schema-taxonomies",
      label: "Go to Taxonomies",
      description: "Manage taxonomy definitions",
      onSelect: () => {
        navigate({ to: "/app/schema/taxonomies" }).catch(() => {});
      },
    },
    {
      id: "open-schema-classes",
      label: "Go to Classes",
      description: "Manage class definitions",
      onSelect: () => {
        navigate({ to: "/app/schema/classes" }).catch(() => {});
      },
    },
    {
      id: "open-data-individuals",
      label: "Go to Individuals",
      description: "Manage individual instances",
      onSelect: () => {
        navigate({ to: "/app/data/individuals" }).catch(() => {});
      },
    },
    {
      id: "open-pipelines",
      label: "Go to Pipelines",
      description: "Manage LLM pipelines",
      onSelect: () => {
        navigate({ to: "/app/pipelines" }).catch(() => {});
      },
    },
    {
      id: "open-settings",
      label: "Open Settings",
      description: "Configure application settings",
      onSelect: () => {
        navigate({ to: "/app/settings" }).catch(() => {});
      },
    },
    {
      id: "show-help",
      label: "Show Keyboard Shortcuts",
      description: "View command palette help",
      onSelect: () => {
        window.dispatchEvent(new CustomEvent("show-command-palette-help"));
      },
    },
  ];
}

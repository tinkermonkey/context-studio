import { Outlet, createRootRoute } from "@tanstack/react-router";
import { createTheme, ThemeProvider } from "flowbite-react";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";

const customTheme = createTheme({
  button: {
    color: {
      primary: "#4F46E5",
      secondary: "#6B7280",
    },
  },
  table: {
    root:{
      shadow: "drop-shadow-none",
    },
    head: {
      base: "rounded-none border-t-1 border-gray-300 dark:border-gray-600",
    },
    body: {
      base: "rounded-none border-t-1 border-b-1 border-gray-300 dark:border-gray-600",
    }
  },
});

export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  return (
    <ThemeProvider theme={customTheme}>
      <Outlet />
      <TanStackRouterDevtools position="bottom-right" />
    </ThemeProvider>
  );
}

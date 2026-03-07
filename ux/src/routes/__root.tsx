import { Outlet, createRootRoute } from "@tanstack/react-router";
import { createTheme, ThemeProvider } from "flowbite-react";
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";

const customTheme = createTheme({
  button: {
    color: {
      primary: "#4F46E5",
      secondary: "#6B7280",
    },
  },
  table: {
    root: {
      shadow: "drop-shadow-none",
    },
    head: {
      base: "rounded-none border-t-1 border-gray-300 dark:border-gray-600",
    },
    body: {
      base: "rounded-none border-t-1 border-b-1 border-gray-300 dark:border-gray-600",
    },
  },
  textInput: {
    field: {
      input: {
        sizes: {
          sm: "p-2 sm:text-xs",
          md: "p-2 sm:text-sm",
          lg: "p-2 sm:text-base",
        },
      },
    },
  },
});

export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={customTheme}>
        <Outlet />
        {/* <TanStackRouterDevtools position="bottom-right" /> */}
      </ThemeProvider>
    </QueryClientProvider>
  );
}

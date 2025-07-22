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

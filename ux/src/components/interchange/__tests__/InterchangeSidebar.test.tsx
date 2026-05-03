/**
 * Tests for InterchangeSidebar component
 */

import React from "react";
import { vi } from "vitest";
import {
  renderWithProviders as render,
  screen,
} from "@/test/utils/renderWithProviders";
import { InterchangeSidebar } from "../InterchangeSidebar";

// Mock TanStack Router
vi.mock("@tanstack/react-router", () => ({
  useRouterState: vi.fn(),
  Link: ({ to, children, ...props }: any) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

// Mock the sidebar component
vi.mock("@/components/layout/cs_sidebar", () => ({
  CsSidebar: ({ children }: any) => (
    <aside data-testid="cs-sidebar">{children}</aside>
  ),
  CsSidebarTitle: ({ children }: any) => (
    <h2 data-testid="cs-sidebar-title">{children}</h2>
  ),
}));

describe("InterchangeSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders sidebar container", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange" },
    });

    render(<InterchangeSidebar />);

    expect(screen.getByTestId("cs-sidebar")).toBeInTheDocument();
  });

  it("renders sidebar title", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange" },
    });

    render(<InterchangeSidebar />);

    expect(screen.getByTestId("cs-sidebar-title")).toBeInTheDocument();
    expect(screen.getByText("Interchange")).toBeInTheDocument();
  });

  it("renders navigation links", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange" },
    });

    render(<InterchangeSidebar />);

    expect(screen.getByRole("link", { name: /recent runs/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /export/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /import/i })).toBeInTheDocument();
  });

  it("sets correct links", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange" },
    });

    render(<InterchangeSidebar />);

    const runsLink = screen.getByRole("link", {
      name: /recent runs/i,
    }) as HTMLAnchorElement;
    const exportLink = screen.getByRole("link", {
      name: /export/i,
    }) as HTMLAnchorElement;
    const importLink = screen.getByRole("link", {
      name: /import/i,
    }) as HTMLAnchorElement;

    expect(runsLink.href).toContain("/app/interchange");
    expect(exportLink.href).toContain("/app/interchange/export");
    expect(importLink.href).toContain("/app/interchange/import");
  });

  it("highlights recent runs link when on main interchange page", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange" },
    });

    render(<InterchangeSidebar />);

    const runsLink = screen.getByRole("link", { name: /recent runs/i });
    expect(runsLink.className).toContain("bg-blue");
    expect(runsLink.className).toContain("font-semibold");
  });

  it("highlights export link when on export page", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange/export" },
    });

    render(<InterchangeSidebar />);

    const exportLink = screen.getByRole("link", { name: /export/i });
    expect(exportLink.className).toContain("bg-blue");
    expect(exportLink.className).toContain("font-semibold");
  });

  it("highlights import link when on import page", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange/import" },
    });

    render(<InterchangeSidebar />);

    const importLink = screen.getByRole("link", { name: /import/i });
    expect(importLink.className).toContain("bg-blue");
    expect(importLink.className).toContain("font-semibold");
  });

  it("defaults to runs view when pathname doesn't match export or import", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange/unknown" },
    });

    render(<InterchangeSidebar />);

    const runsLink = screen.getByRole("link", { name: /recent runs/i });
    expect(runsLink.className).toContain("bg-blue");
  });

  it("applies correct styling to non-active links", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange/export" },
    });

    render(<InterchangeSidebar />);

    const importLink = screen.getByRole("link", { name: /import/i });
    // Non-active links should not have blue background
    expect(importLink.className).not.toContain("bg-blue-100");
    expect(importLink.className).toContain("text-gray");
    expect(importLink.className).toContain("hover:");
  });

  it("renders nav element with space between links", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange" },
    });

    const { container } = render(<InterchangeSidebar />);

    const nav = container.querySelector("nav");
    expect(nav).toBeInTheDocument();
    expect(nav?.className).toContain("space-y");
  });

  it("handles root interchange path correctly", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange/" },
    });

    render(<InterchangeSidebar />);

    const runsLink = screen.getByRole("link", { name: /recent runs/i });
    expect(runsLink.className).toContain("bg-blue");
  });

  it("renders all links with proper structure", () => {
    const { useRouterState } = require("@tanstack/react-router");
    useRouterState.mockReturnValue({
      location: { pathname: "/app/interchange" },
    });

    const { container } = render(<InterchangeSidebar />);

    const links = container.querySelectorAll("nav a");
    expect(links.length).toBe(3); // Recent Runs, Export, Import
  });
});

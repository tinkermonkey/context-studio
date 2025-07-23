
import {
  Badge,
  Dropdown,
  DropdownItem,
  Navbar,
  NavbarBrand,
  NavbarCollapse,
  NavbarLink,
  TextInput,
} from "flowbite-react";
import { Search } from "lucide-react";
import { useMatchRoute } from "@tanstack/react-router";

export function CsNavbar() {
  const matchRoute = useMatchRoute();

  return (
    <Navbar className="sticky top-0 z-[60] p-0 mx-auto flex w-full items-center justify-between border-b border-gray-200 bg-white text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between px-4 py-2.5 lg:px-4">
        <div className="flex items-center">
          <NavbarBrand href="/" className="flex items-center gap-3 text-2xl font-semibold text-gray-900 dark:text-white">
              Context Studio
          </NavbarBrand>
          <TextInput
            className="hidden ml-[6rem] w-64 lg:flex"
            placeholder="Search..."
            type="search"
            icon={Search}
            aria-label="Search"
          />
        </div>
        <div className="flex items-center">
          <NavbarCollapse>
            <NavbarLink href="/app" active={!!matchRoute({ to: "/app", fuzzy: false })}>Dashboard</NavbarLink>
            <NavbarLink href="/app/layers" active={!!matchRoute({ to: "/app/layers", fuzzy: true })}>Layers</NavbarLink>
            <NavbarLink href="/app/domains" active={!!matchRoute({ to: "/app/domains", fuzzy: true })}>Domains</NavbarLink>
            <NavbarLink href="/app/terms" active={!!matchRoute({ to: "/app/terms", fuzzy: true })}>Terms</NavbarLink>
          </NavbarCollapse>
        </div>
        <Badge className="hidden lg:block" color="info">v0.1.0</Badge>
      </div>
    </Navbar>
  );
}

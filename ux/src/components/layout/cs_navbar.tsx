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
    <Navbar className="sticky top-0 z-[60] mx-auto flex w-full items-center justify-between border-b border-gray-200 bg-white p-0 text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between px-4 py-2.5 lg:px-4">
        <div className="flex items-center">
          <NavbarBrand
            href="/"
            className="flex items-center gap-3 text-2xl font-semibold text-gray-900 dark:text-white"
          >
            Context Studio
          </NavbarBrand>
          <TextInput
            className="ml-[6rem] hidden w-64 lg:flex"
            placeholder="Search..."
            type="search"
            icon={Search}
            aria-label="Search"
          />
        </div>
        <div className="flex items-center">
          <NavbarCollapse>
            <NavbarLink
              href="/app"
              active={!!matchRoute({ to: "/app", fuzzy: false })}
            >
              Dashboard
            </NavbarLink>
            <NavbarLink
              href="/app/datasets"
              active={!!matchRoute({ to: "/app/datasets", fuzzy: false })}
            >
              Datasets
            </NavbarLink>

            <Dropdown
              label="Structure"
              className="hidden lg:block"
              inline={true}
            >
              <DropdownItem href="/app/layers">Layers</DropdownItem>
              <DropdownItem href="/app/domains">Domains</DropdownItem>
              <DropdownItem href="/app/terms">Terms</DropdownItem>
              <DropdownItem href="/app/predicates">Predicates</DropdownItem>
            </Dropdown>
            <Dropdown
              label="Reference"
              className="hidden lg:block"
              inline={true}
            >
              <DropdownItem href="/app/reference/search">Search</DropdownItem>
              <DropdownItem href="/app/reference/predicates">
                Predicates
              </DropdownItem>
              <DropdownItem href="/app/reference/rag-test">
                RAG Test
              </DropdownItem>
            </Dropdown>
            <Dropdown label="Data" className="hidden lg:block" inline={true}>
              <DropdownItem href="/app/data/sources">Sources</DropdownItem>
              <DropdownItem href="/app/data/transformations">
                Transformations
              </DropdownItem>
              <DropdownItem href="/app/data/visualizations">
                Visualizations
              </DropdownItem>
            </Dropdown>
            <Dropdown label="Config" className="hidden lg:block" inline={true}>
              <DropdownItem href="/app/config/pipelines">
                Pipeline Flavors
              </DropdownItem>
              <DropdownItem href="/app/config/schema">Schema.org</DropdownItem>
              <DropdownItem href="/app/config/datasets">
                Dataset Settings
              </DropdownItem>
            </Dropdown>
          </NavbarCollapse>
        </div>
        <Badge className="hidden lg:block" color="info">
          v0.1.0
        </Badge>
      </div>
    </Navbar>
  );
}

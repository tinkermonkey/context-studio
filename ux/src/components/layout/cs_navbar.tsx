import { Badge, Dropdown, DropdownItem, Navbar, NavbarBrand, NavbarCollapse, NavbarLink, NavbarToggle, TextInput  } from "flowbite-react";;
import { Search, Settings } from "lucide-react";
import { useMatchRoute } from "@tanstack/react-router";

/**
 * Mobile navigation menu component
 * Provides a flat navigation structure for mobile devices with category prefixes
 */
function MobileNavMenu() {
  return (
    <div className="lg:hidden">
      {/* Knowledge Graph Items */}
      <NavbarLink href="/app/layers">KG: Layers</NavbarLink>
      <NavbarLink href="/app/domains">KG: Domains</NavbarLink>
      <NavbarLink href="/app/terms">KG: Terms</NavbarLink>
      <NavbarLink href="/app/predicates">KG: Predicates</NavbarLink>

      {/* RAG & Testing Items */}
      <NavbarLink href="/app/rag/experiments">RAG: Experiments</NavbarLink>
      <NavbarLink href="/app/rag/pipeline-comparison">
        RAG: Pipeline Comparison
      </NavbarLink>
      <NavbarLink href="/app/rag/test-runner">RAG: Test Runner</NavbarLink>

      {/* External Reference Items */}
      <NavbarLink href="/app/reference/search">Ref: Search</NavbarLink>
      <NavbarLink href="/app/reference/predicates">
        Ref: Predicate Mapping
      </NavbarLink>

      {/* Configuration */}
      <NavbarLink href="/app/config">Configuration</NavbarLink>
    </div>
  );
}

/**
 * Desktop navigation dropdown menus
 * Provides hierarchical navigation structure for desktop devices
 */
function DesktopNavMenus() {
  return (
    <>
      {/* Knowledge Graph */}
      <Dropdown
        label="Knowledge Graph"
        className="hidden lg:block"
        inline={true}
      >
        <DropdownItem href="/app/layers">Layers</DropdownItem>
        <DropdownItem href="/app/domains">Domains</DropdownItem>
        <DropdownItem href="/app/terms">Terms</DropdownItem>
        <DropdownItem href="/app/predicates">Predicates</DropdownItem>
      </Dropdown>

      {/* RAG & Testing */}
      <Dropdown label="RAG & Testing" className="hidden lg:block" inline={true}>
        <DropdownItem href="/app/rag/experiments">Experiments</DropdownItem>
        <DropdownItem href="/app/rag/pipeline-comparison">
          Pipeline Comparison
        </DropdownItem>
        <DropdownItem href="/app/rag/test-runner">Test Runner</DropdownItem>
      </Dropdown>

      {/* External Reference */}
      <Dropdown
        label="External Reference"
        className="hidden lg:block"
        inline={true}
      >
        <DropdownItem href="/app/reference/search">Search</DropdownItem>
        <DropdownItem href="/app/reference/predicates">
          Predicate Mapping
        </DropdownItem>
      </Dropdown>
    </>
  );
}

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
        <div className="flex items-center gap-2">
          <NavbarToggle />
          <NavbarCollapse>
            {/* Dashboard */}
            <NavbarLink
              href="/app"
              active={!!matchRoute({ to: "/app", fuzzy: false })}
            >
              Dashboard
            </NavbarLink>

            {/* Desktop Navigation Dropdowns */}
            <DesktopNavMenus />

            {/* Datasets */}
            <NavbarLink
              href="/app/datasets"
              active={!!matchRoute({ to: "/app/datasets", fuzzy: false })}
            >
              Datasets
            </NavbarLink>

            {/* Mobile Navigation */}
            <MobileNavMenu />
          </NavbarCollapse>

          {/* Right side: Config icon and version badge */}
          <Dropdown
            label=""
            dismissOnClick={true}
            renderTrigger={() => (
              <button
                className="hidden rounded-lg p-2 text-gray-500 hover:bg-gray-100 focus:ring-4 focus:ring-gray-200 focus:outline-none lg:block dark:text-gray-400 dark:hover:bg-gray-700 dark:focus:ring-gray-700"
                aria-label="Configuration menu"
              >
                <Settings className="h-5 w-5" />
              </button>
            )}
            inline={true}
            className="hidden lg:block"
          >
            <DropdownItem href="/app/config">Configuration</DropdownItem>
            <DropdownItem href="/app/config/pipelines">
              Pipeline Flavors
            </DropdownItem>
            <DropdownItem href="/app/config/models">Models</DropdownItem>
            <DropdownItem href="/app/config/data-sources">
              Data Sources
            </DropdownItem>
            <DropdownItem href="/app/config/processing">
              Processing
            </DropdownItem>
            <DropdownItem href="/app/config/system">System</DropdownItem>
            <DropdownItem href="/app/config/network">Network</DropdownItem>
            <DropdownItem href="/app/config/advanced">Advanced</DropdownItem>
          </Dropdown>

          <Badge className="hidden lg:block" color="info">
            v0.1.0
          </Badge>
        </div>
      </div>
    </Navbar>
  );
}

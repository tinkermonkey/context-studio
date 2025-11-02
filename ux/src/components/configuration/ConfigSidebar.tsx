import { Link, useRouterState } from "@tanstack/react-router";
import { Card } from "flowbite-react";
import {
  Brain,
  Database,
  Zap,
  Server,
  Globe,
  Cog,
  Settings,
  Shield
} from "lucide-react";

interface ConfigSection {
  id: string;
  title: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  priority?: boolean;
  expert?: boolean;
}

const CONFIG_SECTIONS: ConfigSection[] = [
  {
    id: "models",
    title: "LLM Models",
    path: "/app/config/models",
    icon: Brain,
    description: "Manage available models and providers",
    priority: true,
  },
  {
    id: "data-sources",
    title: "Data Sources",
    path: "/app/config/data-sources",
    icon: Database,
    description: "Reference APIs and database settings",
  },
  {
    id: "processing",
    title: "Processing",
    path: "/app/config/processing",
    icon: Zap,
    description: "NLP configuration and pipeline defaults",
  },
  {
    id: "system",
    title: "System",
    path: "/app/config/system",
    icon: Server,
    description: "Server settings, logging, and security",
  },
  {
    id: "network",
    title: "Network & Proxy",
    path: "/app/config/network",
    icon: Globe,
    description: "Proxy server and caching configuration",
  },
  {
    id: "advanced",
    title: "Advanced",
    path: "/app/config/advanced",
    icon: Cog,
    description: "Raw configuration and advanced tools",
    expert: true,
  },
];

export function ConfigSidebar() {
  const router = useRouterState();
  const currentPath = router.location.pathname;

  return (
    <div className="space-y-4">
      {/* Overview Section */}
      <div className="p-4">
        <div className="flex items-center gap-3 mb-3">
          <Settings className="h-5 w-5 text-gray-600" />
          <h3 className="font-semibold text-gray-900">Configuration</h3>
        </div>

        <Link
          to="/app/config"
          className={`block px-3 py-2 rounded-md text-sm transition-colors ${
            currentPath === "/app/config"
              ? "bg-blue-100 text-blue-800 font-medium"
              : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
          }`}
        >
          Overview
        </Link>
      </div>

      {/* Pipeline Configuration */}
      <div className="p-4">
        <h4 className="font-medium text-gray-900 mb-3 text-sm uppercase tracking-wide">
          Pipeline Management
        </h4>

        <Link
          to="/app/config/pipelines"
          className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
            currentPath.startsWith("/app/config/pipelines")
              ? "bg-blue-100 text-blue-800 font-medium"
              : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
          }`}
        >
          <Shield className="h-4 w-4 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="truncate">Pipeline Flavors</span>
            <p className="text-xs text-gray-500 mt-0.5 truncate">
              Manage LLM pipeline configurations
            </p>
          </div>
        </Link>
      </div>

      {/* Configuration Sections */}
      <div className="p-4">
        <h4 className="font-medium text-gray-900 mb-3 text-sm uppercase tracking-wide">
          Settings
        </h4>

        <nav className="space-y-1">
          {CONFIG_SECTIONS.map((section) => {
            const Icon = section.icon;
            const isActive = currentPath === section.path;

            return (
              <Link
                key={section.id}
                to={section.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-blue-100 text-blue-800 font-medium"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate">{section.title}</span>
                    {section.priority && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                        Priority
                      </span>
                    )}
                    {section.expert && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                        Expert
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5 truncate">
                    {section.description}
                  </p>
                </div>
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
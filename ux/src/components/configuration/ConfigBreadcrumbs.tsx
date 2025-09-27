import { Link } from "@tanstack/react-router";
import { Breadcrumb } from "flowbite-react";
import { Home } from "lucide-react";

interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface ConfigBreadcrumbsProps {
  items: BreadcrumbItem[];
}

export function ConfigBreadcrumbs({ items }: ConfigBreadcrumbsProps) {
  const baseBreadcrumbs: BreadcrumbItem[] = [
    { label: "Home", path: "/app" },
    { label: "Configuration", path: "/app/config" },
  ];

  const allBreadcrumbs = [...baseBreadcrumbs, ...items];

  return (
    <Breadcrumb className="mb-4">
      <div className="flex items-center space-x-2 text-sm text-gray-500">
        {allBreadcrumbs.map((item, index) => (
          <div key={index} className="flex items-center">
            {index > 0 && <span className="mx-2">/</span>}

            {item.path ? (
              <Link
                to={item.path}
                className="flex items-center gap-1 hover:text-blue-600 transition-colors"
              >
                {index === 0 && <Home className="h-4 w-4" />}
                {item.label}
              </Link>
            ) : (
              <span className="text-gray-900 dark:text-white font-medium">
                {item.label}
              </span>
            )}
          </div>
        ))}
      </div>
    </Breadcrumb>
  );
}
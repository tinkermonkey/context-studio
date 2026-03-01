import { Card } from "flowbite-react";
import { ArrowRight, LucideIcon } from "lucide-react";
import { Link } from "@tanstack/react-router";

interface QuickActionCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  href: string;
}

export function QuickActionCard({
  title,
  description,
  icon: Icon,
  href,
}: QuickActionCardProps) {
  return (
    <Link to={href} className="group block">
      <Card className="hover:border-primary-500 focus-visible:ring-primary-500 h-full transition-all duration-200 hover:shadow-lg focus-visible:ring-2 focus-visible:outline-none">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="mb-2 flex items-center gap-3">
              <Icon
                className="text-primary-600 dark:text-primary-400 group-hover:text-primary-700 dark:group-hover:text-primary-300 h-5 w-5 transition-colors"
                aria-hidden="true"
              />
              <h3 className="group-hover:text-primary-700 dark:group-hover:text-primary-300 text-lg font-semibold text-gray-900 transition-colors dark:text-white">
                {title}
              </h3>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {description}
            </p>
          </div>
          <ArrowRight
            className="group-hover:text-primary-600 dark:group-hover:text-primary-400 ml-2 h-5 w-5 flex-shrink-0 text-gray-400 transition-all group-hover:translate-x-1"
            aria-hidden="true"
          />
        </div>
      </Card>
    </Link>
  );
}

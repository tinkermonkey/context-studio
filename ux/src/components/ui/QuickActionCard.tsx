import { Card } from 'flowbite-react';
import { ArrowRight, LucideIcon } from 'lucide-react';
import { Link } from '@tanstack/react-router';

interface QuickActionCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  href: string;
}

export function QuickActionCard({ title, description, icon: Icon, href }: QuickActionCardProps) {
  return (
    <Link to={href} className="block group">
      <Card className="h-full hover:shadow-lg transition-all duration-200 hover:border-primary-500 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <Icon
                className="h-5 w-5 text-primary-600 dark:text-primary-400 group-hover:text-primary-700 dark:group-hover:text-primary-300 transition-colors"
                aria-hidden="true"
              />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white group-hover:text-primary-700 dark:group-hover:text-primary-300 transition-colors">
                {title}
              </h3>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {description}
            </p>
          </div>
          <ArrowRight
            className="h-5 w-5 text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-400 group-hover:translate-x-1 transition-all flex-shrink-0 ml-2"
            aria-hidden="true"
          />
        </div>
      </Card>
    </Link>
  );
}

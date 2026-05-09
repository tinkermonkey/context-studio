import { Card } from "flowbite-react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: number | string;
  icon: LucideIcon;
  iconColor: string;
  loading?: boolean;
}

export function StatCard({
  title,
  value,
  icon: Icon,
  iconColor,
  loading = false,
}: StatCardProps) {
  return (
    <Card className="transition-shadow duration-200 hover:shadow-lg">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {title}
          </p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
            {loading ? "..." : value.toLocaleString()}
          </p>
        </div>
        <div className={`rounded-full p-3 ${iconColor}`}>
          <Icon className="h-6 w-6 text-white" aria-hidden="true" />
        </div>
      </div>
    </Card>
  );
}

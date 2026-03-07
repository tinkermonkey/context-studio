/**
 * LoadingSkeleton Component
 *
 * Reusable loading skeleton components for displaying placeholder content
 * during async operations. Improves perceived performance and UX.
 */

import React from "react";

interface SkeletonProps {
  className?: string;
}

/**
 * Base skeleton component with pulse animation
 */
export const Skeleton: React.FC<SkeletonProps> = ({ className = "" }) => {
  return (
    <div
      className={`animate-skeleton-pulse rounded-md bg-gray-200 ${className}`}
      aria-hidden="true"
    />
  );
};

/**
 * Skeleton for text lines
 */
export const TextSkeleton: React.FC<{
  lines?: number;
  className?: string;
}> = ({ lines = 3, className = "" }) => {
  return (
    <div className={`space-y-2 ${className}`} aria-label="Loading content">
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={index}
          className={`h-4 ${index === lines - 1 ? "w-3/4" : "w-full"}`}
        />
      ))}
    </div>
  );
};

/**
 * Skeleton for a card component
 */
export const CardSkeleton: React.FC<SkeletonProps> = ({ className = "" }) => {
  return (
    <div
      className={`rounded-lg border-2 border-gray-200 p-4 ${className}`}
      aria-label="Loading card"
    >
      <Skeleton className="mb-4 h-6 w-1/3" />
      <TextSkeleton lines={2} />
    </div>
  );
};

/**
 * Skeleton for word sense cards
 */
export const WordSenseCardSkeleton: React.FC<{
  count?: number;
}> = ({ count = 3 }) => {
  return (
    <div
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
      aria-label={`Loading ${count} word sense cards`}
    >
      {Array.from({ length: count }).map((_, index) => (
        <CardSkeleton key={index} />
      ))}
    </div>
  );
};

/**
 * Skeleton for reference node list
 */
export const ReferenceNodeSkeleton: React.FC<{
  count?: number;
}> = ({ count = 5 }) => {
  return (
    <div className="space-y-3" aria-label={`Loading ${count} reference nodes`}>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="flex items-center gap-3 rounded-lg border border-gray-200 p-3"
        >
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-4 w-full" />
          </div>
          <Skeleton className="h-8 w-20" />
        </div>
      ))}
    </div>
  );
};

/**
 * Skeleton for table rows
 */
export const TableRowSkeleton: React.FC<{
  rows?: number;
  columns?: number;
}> = ({ rows = 5, columns = 4 }) => {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex} className="border-b">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <td key={colIndex} className="px-6 py-4">
              <Skeleton className="h-4 w-full" />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
};

/**
 * Skeleton for a button
 */
export const ButtonSkeleton: React.FC<SkeletonProps> = ({ className = "" }) => {
  return <Skeleton className={`h-10 w-24 rounded-lg ${className}`} />;
};

/**
 * Full page loading skeleton
 */
export const PageSkeleton: React.FC = () => {
  return (
    <div className="space-y-6 p-6" aria-label="Loading page">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-1/3" />
        <ButtonSkeleton />
      </div>
      <Skeleton className="h-px w-full" />
      <div className="space-y-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    </div>
  );
};

export default Skeleton;

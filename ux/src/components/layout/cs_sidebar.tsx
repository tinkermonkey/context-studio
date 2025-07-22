import React, { ReactNode } from "react";

interface CsSidebarProps {
  children?: ReactNode;
}

const CsSidebar: React.FC<CsSidebarProps> = ({ children }) => {
  return (
    <div className="fixed inset-0 z-50 hidden size-full max-w-64 overflow-y-auto bg-white lg:sticky lg:top-[61px] lg:block lg:h-[calc(100vh-4rem)] dark:bg-gray-900 pt-8">
      <nav className="px-1 pb-8 pl-3 pt-16 text-base font-normal lg:pl-0 lg:pt-2 lg:text-sm" aria-label="Main Sidebar">
        {children}
      </nav>
    </div>
  );
};

const CsSidebarTitle: React.FC<CsSidebarProps> = ({ children }) => {
  return (
    <div className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-900 lg:text-xs dark:text-white">
      {children}
    </div>
  );
};

export { CsSidebar, CsSidebarTitle };

import React, { ReactNode } from "react";

interface CsMainProps {
  children?: ReactNode;
}

const CsMain: React.FC<CsMainProps> = ({ children }) => {
  return (
    <div className="w-full min-w-0 overflow-x-auto p-2">
      {children}
    </div>
  );
};

const CsMainTitle: React.FC<CsMainProps> = ({ children }) => {
  return (
    <div className="pt-6 pb-4 text-3xl font-semibold text-gray-900 dark:text-white">
      {children}
    </div>
  );
};

export { CsMain, CsMainTitle };

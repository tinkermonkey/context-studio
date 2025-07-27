import React, { ReactNode } from "react";

interface CsMainProps {
  children?: ReactNode;
}

interface CsMainTitleProps {
  children?: ReactNode;
  icon?: React.ComponentType<any>;
}

const CsMain: React.FC<CsMainProps> = ({ children }) => {
  return (
    <div className="w-full min-w-0 overflow-x-auto p-2">
      {children}
    </div>
  );
};

const CsMainTitle: React.FC<CsMainTitleProps> = ({ children, icon: Icon }) => {
  return (
    <div className="pt-6 pb-4 text-3xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
      {Icon && <Icon className="mr-2 inline align-baseline" />}
      {children}
    </div>
  );
};

export { CsMain, CsMainTitle };

import React, { ReactNode } from "react";

interface CsMainProps {
  children?: ReactNode;
}

interface CsMainTitleProps {
  children?: ReactNode;
  icon?: React.ComponentType<any>;
  className?: string;
}

const CsMain: React.FC<CsMainProps> = ({ children }) => {
  return <div className="w-full min-w-0 overflow-x-auto p-2 pt-8">{children}</div>;
};

const CsMainTitle: React.FC<CsMainTitleProps> = ({
  children,
  icon: Icon,
  className,
}) => {
  return (
    <div
      className={`flex items-center gap-2 pb-4 text-3xl font-semibold text-gray-900 dark:text-white ${className}`}
    >
      {Icon && <Icon className="mr-2 inline align-baseline" />}
      {children}
    </div>
  );
};

export { CsMain, CsMainTitle };

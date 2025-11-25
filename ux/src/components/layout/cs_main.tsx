import React, { ReactNode } from "react";

interface CsMainProps {
  children?: ReactNode;
}

interface CsMainTitleProps {
  children?: ReactNode;
  icon?: React.ComponentType<any>;
  className?: string;
  'data-testid'?: string;
}

interface CsMainHeaderProps {
  children?: ReactNode;
  className?: string;
}

const CsMain: React.FC<CsMainProps> = ({ children }) => {
  return <div className="w-full min-w-0 pl-2">{children}</div>;
};

const CsMainTitle: React.FC<CsMainTitleProps> = ({
  children,
  icon: Icon,
  className,
  'data-testid': dataTestId,
}) => {
  return (
    <div
      className={`flex items-center gap-2 pb-4 text-3xl font-semibold text-gray-900 dark:text-white ${className}`}
      data-testid={dataTestId}
    >
      {Icon && <Icon className="mr-2 inline align-baseline" />}
      {children}
    </div>
  );
};

const CsMainHeader: React.FC<CsMainHeaderProps> = ({ children, className }) => {
  return (
    <div
      className={`sticky z-10 bg-white dark:bg-gray-900 pb-4 ${className || ""}`}
      style={{ top: "var(--navbar-height, 0px)" }}
    >
      {children}
    </div>
  );
};

export { CsMain, CsMainTitle, CsMainHeader };

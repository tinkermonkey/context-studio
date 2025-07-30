/**
 * API Error Boundary Component
 * 
 * React component for handling and displaying API errors
 */

import React, { Component, ReactNode } from 'react';
import { Alert } from 'flowbite-react';
import { ApiError, ValidationError } from '../../api/errors/ApiError';
import { 
  isValidationError, 
  isNetworkError, 
  isServerError,
  getErrorMessage,
  getDetailedErrorInfo 
} from '../../api/errors/errorHandlers';

interface Props {
  children: ReactNode;
  fallback?: (error: Error, errorInfo: React.ErrorInfo) => ReactNode;
  showDetails?: boolean;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class ApiErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });
    
    // Call the optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
    
    // Log the error
    console.error('API Error Boundary caught an error:', error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.state.errorInfo!);
      }

      // Default error display
      return this.renderDefaultError();
    }

    return this.props.children;
  }

  private renderDefaultError() {
    const { error } = this.state;
    const { showDetails = false } = this.props;
    
    if (!error) return null;

    const errorInfo = getDetailedErrorInfo(error);
    const isNetwork = isNetworkError(error);
    const isServer = isServerError(error);
    const isValidation = isValidationError(error);

    let alertColor: "failure" | "warning" | "info" = "failure";
    let title = "Error";

    if (isNetwork) {
      alertColor = "warning";
      title = "Connection Error";
    } else if (isServer) {
      alertColor = "failure";
      title = "Server Error";
    } else if (isValidation) {
      alertColor = "info";
      title = "Validation Error";
    }

    return (
      <div className="p-4">
        <Alert color={alertColor} className="mb-4">
          <div className="flex flex-col space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium">{title}</h3>
              <button
                onClick={this.handleRetry}
                className="text-sm underline hover:no-underline"
              >
                Try Again
              </button>
            </div>
            
            <p className="text-sm">{getErrorMessage(error)}</p>
            
            {isValidation && errorInfo.validationErrors && (
              <div className="mt-2">
                <p className="text-sm font-medium mb-1">Validation Errors:</p>
                <ul className="text-sm list-disc list-inside space-y-1">
                  {Object.entries(errorInfo.validationErrors).map(([field, errors]) => (
                    <li key={field}>
                      <strong>{field}:</strong> {errors.join(', ')}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {showDetails && (
              <details className="mt-2">
                <summary className="text-sm font-medium cursor-pointer">
                  Technical Details
                </summary>
                <div className="mt-2 p-2 bg-gray-100 rounded text-xs">
                  <p><strong>Status:</strong> {errorInfo.status}</p>
                  <p><strong>Code:</strong> {errorInfo.code}</p>
                  {error instanceof ApiError && error.endpoint && (
                    <p><strong>Endpoint:</strong> {error.method} {error.endpoint}</p>
                  )}
                                    {errorInfo.detail !== undefined && (
                    <div>
                      <strong>Detail:</strong>
                      <pre className="mt-1 overflow-auto">
                        {(() => {
                          try {
                            return typeof errorInfo.detail === 'string' 
                              ? errorInfo.detail 
                              : JSON.stringify(errorInfo.detail, null, 2);
                          } catch {
                            return String(errorInfo.detail);
                          }
                        })()}
                      </pre>
                    </div>
                  )}
                </div>
              </details>
            )}
          </div>
        </Alert>
      </div>
    );
  }
}

/**
 * HOC for wrapping components with API error boundary
 */
export function withApiErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<Props, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ApiErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ApiErrorBoundary>
  );
  
  WrappedComponent.displayName = `withApiErrorBoundary(${Component.displayName || Component.name})`;
  
  return WrappedComponent;
}

/**
 * Simple error display component for inline errors
 */
interface InlineErrorProps {
  error: unknown;
  className?: string;
  showDetails?: boolean;
}

export const InlineApiError: React.FC<InlineErrorProps> = ({ 
  error, 
  className = "",
  showDetails = false 
}) => {
  if (!error) return null;

  const errorInfo = getDetailedErrorInfo(error);
  const isValidation = isValidationError(error);

  return (
    <div className={`text-red-600 text-sm ${className}`}>
      <p>{getErrorMessage(error)}</p>
      
      {isValidation && errorInfo.validationErrors && (
        <ul className="mt-1 list-disc list-inside space-y-1">
          {Object.entries(errorInfo.validationErrors).map(([field, errors]) => (
            <li key={field}>
              <strong>{field}:</strong> {errors.join(', ')}
            </li>
          ))}
        </ul>
      )}
      
      {showDetails && errorInfo.detail !== undefined && (
        <details className="mt-2">
          <summary className="cursor-pointer">Details</summary>
          <pre className="mt-1 text-xs overflow-auto">
            {(() => {
              try {
                return typeof errorInfo.detail === 'string' 
                  ? errorInfo.detail 
                  : JSON.stringify(errorInfo.detail, null, 2);
              } catch {
                return String(errorInfo.detail);
              }
            })()}
          </pre>
        </details>
      )}
    </div>
  );
};

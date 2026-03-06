/**
 * useButterToast Hook
 *
 * Hook for displaying toast notifications using Flowbite React's Toast component
 */

import { useCallback } from "react";
import { Toast } from "flowbite-react";
import { Check, X, AlertTriangle, Info } from "lucide-react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastOptions {
  type: ToastType;
  message: string;
  duration?: number; // in milliseconds, default 5000
}

/**
 * Hook for displaying toast notifications
 * @returns {Function} showToast - Function to display a toast notification
 */
export const useButterToast = () => {
  const showToast = useCallback(
    ({ type, message, duration = 5000 }: ToastOptions) => {
      // Create toast container if it doesn't exist
      let toastContainer = document.getElementById("toast-container");
      if (!toastContainer) {
        toastContainer = document.createElement("div");
        toastContainer.id = "toast-container";
        toastContainer.className =
          "fixed top-4 right-4 z-50 flex flex-col gap-2";
        document.body.appendChild(toastContainer);
      }

      // Create toast element
      const toastWrapper = document.createElement("div");
      toastContainer.appendChild(toastWrapper);

      // Map type to icon and color
      const iconMap = {
        success: Check,
        error: X,
        warning: AlertTriangle,
        info: Info,
      };

      const Icon = iconMap[type];

      // Render toast using React
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const root = (window as any).ReactDOM?.createRoot?.(toastWrapper);
      if (root) {
        root.render(
          <Toast>
            <div
              className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                type === "success"
                  ? "bg-green-100 text-green-500 dark:bg-green-800 dark:text-green-200"
                  : type === "error"
                    ? "bg-red-100 text-red-500 dark:bg-red-800 dark:text-red-200"
                    : type === "warning"
                      ? "bg-orange-100 text-orange-500 dark:bg-orange-700 dark:text-orange-200"
                      : "bg-blue-100 text-blue-500 dark:bg-blue-800 dark:text-blue-200"
              }`}
            >
              <Icon className="h-5 w-5" />
            </div>
            <div className="ml-3 text-sm font-normal">{message}</div>
            <Toast.Toggle onDismiss={() => toastWrapper.remove()} />
          </Toast>,
        );

        // Auto-dismiss after duration
        setTimeout(() => {
          root.unmount();
          toastWrapper.remove();
        }, duration);
      } else {
        // Fallback to simple DOM manipulation if React root is not available
        toastWrapper.innerHTML = `
        <div class="flex items-center w-full max-w-xs p-4 mb-4 text-gray-500 bg-white rounded-lg shadow dark:text-gray-400 dark:bg-gray-800" role="alert">
          <div class="inline-flex items-center justify-center flex-shrink-0 w-8 h-8 ${
            type === "success"
              ? "text-green-500 bg-green-100 rounded-lg dark:bg-green-800 dark:text-green-200"
              : type === "error"
                ? "text-red-500 bg-red-100 rounded-lg dark:bg-red-800 dark:text-red-200"
                : type === "warning"
                  ? "text-orange-500 bg-orange-100 rounded-lg dark:bg-orange-700 dark:text-orange-200"
                  : "text-blue-500 bg-blue-100 rounded-lg dark:bg-blue-800 dark:text-blue-200"
          }">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              ${
                type === "success"
                  ? '<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>'
                  : type === "error"
                    ? '<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>'
                    : '<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>'
              }
            </svg>
          </div>
          <div class="ml-3 text-sm font-normal">${message}</div>
          <button type="button" class="ml-auto -mx-1.5 -my-1.5 bg-white text-gray-400 hover:text-gray-900 rounded-lg focus:ring-2 focus:ring-gray-300 p-1.5 hover:bg-gray-100 inline-flex h-8 w-8 dark:text-gray-500 dark:hover:text-white dark:bg-gray-800 dark:hover:bg-gray-700" onclick="this.parentElement.remove()">
            <span class="sr-only">Close</span>
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
          </button>
        </div>
      `;

        setTimeout(() => {
          toastWrapper.remove();
        }, duration);
      }
    },
    [],
  );

  return {
    /**
     * Show a success toast notification
     * @param {string} message - The message to display
     * @param {number} duration - Duration in milliseconds (default 5000)
     */
    success: useCallback(
      (message: string, duration?: number) =>
        showToast({ type: "success", message, duration }),
      [showToast],
    ),

    /**
     * Show an error toast notification
     * @param {string} message - The message to display
     * @param {number} duration - Duration in milliseconds (default 5000)
     */
    error: useCallback(
      (message: string, duration?: number) =>
        showToast({ type: "error", message, duration }),
      [showToast],
    ),

    /**
     * Show a warning toast notification
     * @param {string} message - The message to display
     * @param {number} duration - Duration in milliseconds (default 5000)
     */
    warning: useCallback(
      (message: string, duration?: number) =>
        showToast({ type: "warning", message, duration }),
      [showToast],
    ),

    /**
     * Show an info toast notification
     * @param {string} message - The message to display
     * @param {number} duration - Duration in milliseconds (default 5000)
     */
    info: useCallback(
      (message: string, duration?: number) =>
        showToast({ type: "info", message, duration }),
      [showToast],
    ),

    /**
     * Show a toast notification with custom type
     * @param {ToastOptions} options - Toast options including type, message, and duration
     */
    show: showToast,
  };
};

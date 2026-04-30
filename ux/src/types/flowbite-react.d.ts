/**
 * Type augmentation for Flowbite React components
 * Fixes missing type definitions for compound components
 *
 * Note: In flowbite-react v0.11.x, Table components are exported as separate named exports
 * (TableHead, TableCell, etc.) rather than compound components (Table.Head, Table.Cell)
 */

import { ComponentProps, FC, ReactNode } from "react";

declare module "flowbite-react" {
  // Modal props
  export interface ModalProps extends ComponentProps<"div"> {
    show?: boolean;
    onClose?: () => void;
    size?: string;
  }

  // Modal compound component types
  export interface ModalComponent extends FC<ModalProps> {
    Header: FC<ComponentProps<"div">>;
    Body: FC<ComponentProps<"div">>;
    Footer: FC<ComponentProps<"div">>;
  }

  // Export Modal as a compound component
  export const Modal: ModalComponent;

  // Tabs props
  export interface TabsProps extends ComponentProps<"div"> {
    onActiveTabChange?: (index: number) => void;
  }

  // Tabs Item props
  export interface TabsItemProps extends ComponentProps<"div"> {
    active?: boolean;
    title: string;

    icon?: any;
    children?: ReactNode;
  }

  // Tabs compound component types
  export interface TabsComponent extends FC<TabsProps> {
    Item: FC<TabsItemProps>;
  }

  // Export Tabs as a compound component
  export const Tabs: TabsComponent;

  // Toast props
  export type ToastProps = ComponentProps<"div">;

  // Toast Toggle props
  export interface ToastToggleProps extends ComponentProps<"button"> {
    onDismiss?: () => void;
  }

  // Toast compound component types
  export interface ToastComponent extends FC<ToastProps> {
    Toggle: FC<ToastToggleProps>;
  }

  // Export Toast as a compound component
  export const Toast: ToastComponent;
}

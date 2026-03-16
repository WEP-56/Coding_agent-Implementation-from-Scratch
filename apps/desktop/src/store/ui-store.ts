import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ToastKind = "success" | "error" | "info" | "warning";

export interface ToastItem {
  id: string;
  kind: ToastKind;
  title: string;
  message?: string;
}

interface UiState {
  toasts: ToastItem[];
  leftSidebarCollapsed: boolean;
  rightSidebarCollapsed: boolean;
  pushToast: (toast: Omit<ToastItem, "id">, ttlMs?: number) => void;
  removeToast: (id: string) => void;
  setLeftSidebarCollapsed: (collapsed: boolean) => void;
  setRightSidebarCollapsed: (collapsed: boolean) => void;
  toggleLeftSidebar: () => void;
  toggleRightSidebar: () => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      toasts: [],
      leftSidebarCollapsed: false,
      rightSidebarCollapsed: false,
      pushToast: (toast, ttlMs = 3800) => {
        const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        set((state) => ({ toasts: [...state.toasts, { id, ...toast }] }));
        window.setTimeout(() => {
          get().removeToast(id);
        }, ttlMs);
      },
      removeToast: (id) => {
        set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
      },
      setLeftSidebarCollapsed: (collapsed) => {
        set({ leftSidebarCollapsed: collapsed });
      },
      setRightSidebarCollapsed: (collapsed) => {
        set({ rightSidebarCollapsed: collapsed });
      },
      toggleLeftSidebar: () => {
        set((state) => ({ leftSidebarCollapsed: !state.leftSidebarCollapsed }));
      },
      toggleRightSidebar: () => {
        set((state) => ({ rightSidebarCollapsed: !state.rightSidebarCollapsed }));
      },
    }),
    {
      name: "ui-storage",
      partialize: (state) => ({
        leftSidebarCollapsed: state.leftSidebarCollapsed,
        rightSidebarCollapsed: state.rightSidebarCollapsed,
      }),
    },
  ),
);

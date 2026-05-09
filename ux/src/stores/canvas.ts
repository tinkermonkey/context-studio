import { create } from "zustand";
import { persist } from "zustand/middleware";

interface CanvasState {
  darkCanvas: boolean;
  toggleDarkCanvas: () => void;
}

export const useCanvasStore = create<CanvasState>()(
  persist(
    (set) => ({
      darkCanvas: false,
      toggleDarkCanvas: () =>
        set((state) => {
          const next = !state.darkCanvas;
          if (next) {
            document.body.classList.add("dark-canvas");
          } else {
            document.body.classList.remove("dark-canvas");
          }
          return { darkCanvas: next };
        }),
    }),
    {
      name: "canvas-theme",
      onRehydrateStorage: () => (state) => {
        if (state?.darkCanvas) {
          document.body.classList.add("dark-canvas");
        }
      },
    }
  )
);

"use client";

import { useTheme } from "next-themes";
import { Toaster } from "sonner";

/** Sonner defaults to its light theme; follow the app theme so toasts match in dark mode. */
export function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      theme={resolvedTheme === "dark" ? "dark" : "light"}
      position="bottom-left"
      richColors
      closeButton
      toastOptions={{ className: "font-sans" }}
    />
  );
}

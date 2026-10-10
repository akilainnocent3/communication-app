"use client";

import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { MoonIcon, SunIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { cn } from "@/utils/cn";

const subscribe = () => () => {};

export default function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  // The theme is only known on the client; render a neutral icon on the server to avoid a hydration mismatch.
  const mounted = useSyncExternalStore(subscribe, () => true, () => false);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <button
      type="button"
      aria-label={m.shell.theme}
      title={m.shell.theme}
      onClick={() => setTheme(dark ? "light" : "dark")}
      className={cn("flex size-10 items-center justify-center rounded-lg border border-card-border bg-card-background text-icon-primary shadow-xs transition-colors hover:bg-background-gray-secondary_alt focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none", className)}
    >
      {dark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

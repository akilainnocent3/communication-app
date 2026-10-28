"use client";

import type { ReactNode } from "react";
import { BrandLogo } from "@/components/shell/brand";
import ThemeToggle from "@/components/shell/theme-toggle";
import { ActivityIndicator } from "@/components/ui/activity-indicator";

/** Mobile-first frame for the public connect pages: brand header, one centred card, no admin shell. */
export function ConnectFrame({ children, company }: { children: ReactNode; company?: string }) {
  return (
    <main className="h-full overflow-y-auto bg-background-gray-secondary_alt_2 text-text-primary">
      <div className="mx-auto flex min-h-full w-full max-w-xl flex-col px-4 py-5 sm:py-8">
        <header className="mb-5 flex items-center justify-between gap-3">
          <BrandLogo size={32} />
          <ThemeToggle />
        </header>
        <section className="flex-1 animate-fade-up rounded-2xl border border-card-border bg-card-surface-area p-5 shadow-sm sm:p-8">{children}</section>
        <footer className="mt-5 text-center text-xs text-text-tertiary">{company ? `${company} · ` : ""}OCM · Every access is logged</footer>
      </div>
    </main>
  );
}

/** Google's standard light sign-in button (white, multicolour "G", Roboto-weight label) per Google's branding guidelines. */
export function GoogleButton({ onPress, busy, label = "Continue with Google" }: { onPress: () => void; busy?: boolean; label?: string }) {
  return (
    <button
      type="button"
      onClick={onPress}
      disabled={busy}
      className="flex h-14 w-full items-center justify-center gap-3 rounded-full border border-[#747775] bg-white px-6 text-base font-medium text-[#1f1f1f] shadow-sm transition hover:bg-[#f8faff] hover:shadow focus-visible:ring-4 focus-visible:ring-primary-500/40 focus-visible:outline-none disabled:opacity-70 dark:border-[#8e918f] dark:bg-[#131314] dark:text-[#e3e3e3] dark:hover:bg-[#1f1f20]"
    >
      {busy ? <ActivityIndicator size="sm" decorative /> : <GoogleG />}
      <span>{busy ? "Opening Google…" : label}</span>
    </button>
  );
}

function GoogleG() {
  return (
    <svg width="22" height="22" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

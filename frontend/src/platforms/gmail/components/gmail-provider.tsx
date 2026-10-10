"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useSession } from "@/components/shell/session-provider";
import { ComposeManager } from "../compose/compose-manager";
import { openCompose } from "../compose/store";
import { folderUrl } from "../nav";
import { ShortcutHelpDialog, openShortcutHelp, useShortcutDispatcher, useShortcuts } from "../shortcuts";
import { useCurrentMailbox } from "../api/queries";

/** Wraps the shell while Gmail is the active platform: compose windows, keyboard shortcuts and their help. */
export function GmailProvider({ children }: { children: ReactNode }) {
  const { preferences } = useSession();
  const router = useRouter();
  const current = useCurrentMailbox();
  useShortcutDispatcher(preferences.shortcuts);
  useShortcuts({
    c: () => openCompose({ mailbox: current?.id }),
    "/": () => document.getElementById("mail-search")?.focus(),
    "?": openShortcutHelp,
    "g i": () => router.push(folderUrl("inbox")),
    "g s": () => router.push(folderUrl("starred")),
    "g t": () => router.push(folderUrl("sent")),
    "g d": () => router.push(folderUrl("drafts")),
  });
  return (
    <>
      {children}
      <ComposeManager />
      <ShortcutHelpDialog />
    </>
  );
}

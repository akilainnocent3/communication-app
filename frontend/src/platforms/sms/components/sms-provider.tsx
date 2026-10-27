"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useSession } from "@/components/shell/session-provider";
import { useShortcutDispatcher, useShortcuts } from "@/platforms/gmail/shortcuts";
import { useCurrentDevice } from "../api/queries";
import { openNewMessage } from "../compose-store";
import { folderUrl } from "../nav";
import { SmsShortcutHelpDialog, openSmsShortcutHelp } from "../shortcuts";
import { NewMessageDialog } from "./new-message";

/** Wraps the shell while SMS is the active platform: the New message dialog, keyboard shortcuts and their help. */
export function SmsProvider({ children }: { children: ReactNode }) {
  const { preferences } = useSession();
  const router = useRouter();
  const current = useCurrentDevice();
  useShortcutDispatcher(preferences.shortcuts);
  useShortcuts({
    c: () => openNewMessage({ device: current?.id }),
    "?": openSmsShortcutHelp,
    "g i": () => router.push(folderUrl("inbox")),
    "g o": () => router.push("/sms/outbox"),
    "g d": () => router.push("/sms/dashboard"),
  });
  return (
    <>
      {children}
      <NewMessageDialog />
      <SmsShortcutHelpDialog />
    </>
  );
}

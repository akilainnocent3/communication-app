"use client";

import { useSyncExternalStore } from "react";
import type { Address } from "@/services/api/types";

export type ComposeMode = "new" | "reply" | "reply_all" | "forward";

export type ComposeInit = {
  mailbox?: number;
  mode?: ComposeMode;
  to?: Address[];
  cc?: Address[];
  bcc?: Address[];
  subject?: string;
  html?: string;
  threadId?: number;
  inReplyToMessage?: number;
  draftId?: number;
  sendAs?: string;
  attachmentIds?: number[];
  forwardAttachmentIds?: string[];
  /** Names and sizes of forwarded attachments, for display. */
  forwardAttachments?: { id: string; filename: string; size: number }[];
};

export type ComposeWindow = ComposeInit & { key: string; minimized: boolean; maximized: boolean };

let windows: ComposeWindow[] = [];
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((notify) => notify());
let counter = 0;

/** Opens a compose window (re-focuses the existing one for the same draft). At most 3 stay open, like Gmail. */
export function openCompose(init: ComposeInit = {}) {
  const existing = init.draftId ? windows.find((item) => item.draftId === init.draftId) : undefined;
  if (existing) {
    windows = windows.map((item) => (item.key === existing.key ? { ...item, minimized: false } : item));
  } else {
    counter += 1;
    const next: ComposeWindow = { mode: "new", ...init, key: `compose-${Date.now()}-${counter}`, minimized: false, maximized: false };
    windows = [...windows.map((item) => ({ ...item, minimized: windows.length >= 1 ? true : item.minimized })), next].slice(-3);
  }
  emit();
}

export function updateCompose(key: string, patch: Partial<ComposeWindow>) {
  windows = windows.map((item) => (item.key === key ? { ...item, ...patch } : item));
  emit();
}

export function closeCompose(key: string) {
  windows = windows.filter((item) => item.key !== key);
  emit();
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  return () => listeners.delete(notify);
}
const EMPTY: ComposeWindow[] = [];

export function useComposeWindows() {
  return useSyncExternalStore(subscribe, () => windows, () => EMPTY);
}

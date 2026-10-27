"use client";

import { useSyncExternalStore } from "react";

/** The "New message" dialog (sidebar button, FAB, ⌘K, `c`). */
export type NewMessageInit = { device?: string; to?: string };

let state: NewMessageInit | null = null;
const listeners = new Set<() => void>();

export function openNewMessage(init: NewMessageInit = {}) {
  state = init;
  listeners.forEach((notify) => notify());
}

export function closeNewMessage() {
  state = null;
  listeners.forEach((notify) => notify());
}

export function useNewMessage(): NewMessageInit | null {
  return useSyncExternalStore((notify) => { listeners.add(notify); return () => { listeners.delete(notify); }; }, () => state, () => null);
}

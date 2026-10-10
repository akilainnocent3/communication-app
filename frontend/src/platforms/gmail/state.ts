"use client";

import { useSyncExternalStore } from "react";
import { readStored, writeStored } from "@/lib/storage";

/** "all" = unified view across every mailbox the user can open; otherwise a mailbox id. */
export type MailboxScope = "all" | number;

const KEY = "cm:gmail:mailbox";
const listeners = new Set<() => void>();
let scope: MailboxScope | null = null;

function current(): MailboxScope {
  if (scope === null) scope = readStored<MailboxScope>(KEY, "all");
  return scope;
}

export function setMailboxScope(next: MailboxScope) {
  scope = next;
  writeStored(KEY, next);
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

/** The selected mailbox scope (shared by the sidebar switcher, the list and compose). */
export function useMailboxScopeRaw(): MailboxScope {
  return useSyncExternalStore(subscribe, current, () => "all");
}

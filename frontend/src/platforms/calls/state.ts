"use client";

import { useSyncExternalStore } from "react";
import { readStored, writeStored } from "@/lib/storage";

/** "all" = every Calls phone the user can open; otherwise a device id. Separate from SMS's scope. */
export type CallsScope = "all" | string;

const KEY = "cm:calls:device";
const listeners = new Set<() => void>();
let scope: CallsScope | null = null;

function current(): CallsScope {
  if (scope === null) scope = readStored<CallsScope>(KEY, "all");
  return scope;
}

export function setCallsScope(next: CallsScope) {
  scope = next;
  writeStored(KEY, next);
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

export function useCallsScopeRaw(): CallsScope {
  return useSyncExternalStore(subscribe, current, () => "all");
}

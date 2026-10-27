"use client";

import { useSyncExternalStore } from "react";
import { readStored, writeStored } from "@/lib/storage";

/** "all" = unified view across every phone the user can open; otherwise a device id (UUID). */
export type DeviceScope = "all" | string;

const KEY = "cm:sms:device";
const listeners = new Set<() => void>();
let scope: DeviceScope | null = null;

function current(): DeviceScope {
  if (scope === null) scope = readStored<DeviceScope>(KEY, "all");
  return scope;
}

export function setDeviceScope(next: DeviceScope) {
  scope = next;
  writeStored(KEY, next);
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

/** The selected phone scope (shared by the sidebar switcher, lists, dashboard and composer). */
export function useDeviceScopeRaw(): DeviceScope {
  return useSyncExternalStore(subscribe, current, () => "all");
}

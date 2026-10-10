"use client";

import { useSyncExternalStore } from "react";
import { OfflineIcon } from "@/components/ui/icons";
import { m } from "@/i18n";

function subscribe(notify: () => void) {
  window.addEventListener("online", notify);
  window.addEventListener("offline", notify);
  return () => { window.removeEventListener("online", notify); window.removeEventListener("offline", notify); };
}

export function OfflineBanner() {
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
  if (online) return null;
  return (
    <div role="status" aria-live="polite" className="flex items-center justify-center gap-2 bg-warning-500/15 px-4 py-1.5 text-xs font-medium text-text-primary">
      <OfflineIcon size={14} /> {m.common.offline}
    </div>
  );
}

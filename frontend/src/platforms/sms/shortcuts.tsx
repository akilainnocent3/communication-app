"use client";

import { useSyncExternalStore } from "react";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";

/** SMS keyboard shortcuts (same keys as Gmail where the action is the same). The engine is Gmail's useShortcuts. */
export const SMS_SHORTCUT_GROUPS: { title: string; items: [string, string][] }[] = [
  { title: "Navigation", items: [["j / k", "Next / previous conversation"], ["o or Enter", "Open conversation"], ["u", "Back to the list"], ["/", "Search conversations"], ["g then i", "Go to Inbox"], ["g then o", "Go to Outbox"], ["g then d", "Go to Dashboard"], ["⌘K / Ctrl+K", "Command palette"]] },
  { title: "Actions", items: [["c", "New message"], ["Enter", "Send (in the composer)"], ["Shift+Enter", "New line"], ["e", "Archive"], ["!", "Mark as spam"], ["s", "Star / unstar"], ["x", "Select conversation"], ["Shift+I", "Mark as read"], ["Shift+U", "Mark as unread"]] },
  { title: "Help", items: [["?", "Show this list"]] },
];

let open = false;
const listeners = new Set<() => void>();
function setOpen(value: boolean) { open = value; listeners.forEach((notify) => notify()); }
export function openSmsShortcutHelp() { setOpen(true); }

export function SmsShortcutHelpDialog() {
  const isOpen = useSyncExternalStore((notify) => { listeners.add(notify); return () => { listeners.delete(notify); }; }, () => open, () => false);
  return (
    <Dialog isOpen={isOpen} onOpenChange={setOpen} className="max-w-2xl">
      <DialogHeader><DialogTitle>Keyboard shortcuts</DialogTitle></DialogHeader>
      <p className="mt-1 text-sm text-text-tertiary">Turn shortcuts on or off in Settings → Preferences.</p>
      <div className="mt-5 grid max-h-[65vh] gap-6 overflow-y-auto sm:grid-cols-2">
        {SMS_SHORTCUT_GROUPS.map((group) => (
          <section key={group.title}>
            <h3 className="mb-2 text-xs font-semibold tracking-wider text-text-tertiary uppercase">{group.title}</h3>
            <dl className="space-y-1.5">
              {group.items.map(([keys, label]) => (
                <div key={keys} className="flex items-center justify-between gap-3 text-sm">
                  <dt className="text-text-secondary">{label}</dt>
                  <dd><kbd className="rounded-md border border-card-border bg-background-gray-secondary_alt px-2 py-0.5 font-sans text-xs text-text-primary">{keys}</kbd></dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </Dialog>
  );
}

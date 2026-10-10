"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";

/** Gmail keyboard shortcuts. Keys are KeyboardEvent.key values; sequences are written "g i". */
export const SHORTCUT_GROUPS: { title: string; items: [string, string][] }[] = [
  { title: "Navigation", items: [["j / k", "Next / previous conversation"], ["o or Enter", "Open conversation"], ["u", "Back to the list"], ["/", "Search mail"], ["g then i", "Go to Inbox"], ["g then s", "Go to Starred"], ["g then t", "Go to Sent"], ["g then d", "Go to Drafts"], ["⌘K / Ctrl+K", "Command palette"]] },
  { title: "Actions", items: [["c", "Compose"], ["r", "Reply"], ["a", "Reply all"], ["f", "Forward"], ["e", "Archive"], ["#", "Delete"], ["!", "Report spam"], ["s", "Star / unstar"], ["x", "Select conversation"], ["Shift+I", "Mark as read"], ["Shift+U", "Mark as unread"], ["l", "Label"], ["b", "Snooze"]] },
  { title: "Help", items: [["?", "Show this list"]] },
];

type Handler = (event: KeyboardEvent) => void;
type Layer = Record<string, Handler>;

const layers: { id: number; map: Layer }[] = [];
let nextLayer = 1;

/**
 * Registers shortcut handlers while the component is mounted. Later (inner) registrations win, so the open
 * thread can own `r` while the list owns `j`/`k`. Handlers read the latest props through a ref.
 */
export function useShortcuts(map: Layer, enabled = true) {
  const ref = useRef(map);
  useEffect(() => { ref.current = map; });
  const keys = Object.keys(map).sort().join("|");
  useEffect(() => {
    if (!enabled) return;
    const id = nextLayer++;
    const proxy: Layer = {};
    for (const key of keys.split("|")) if (key) proxy[key] = (event) => ref.current[key]?.(event);
    layers.push({ id, map: proxy });
    return () => { const index = layers.findIndex((layer) => layer.id === id); if (index >= 0) layers.splice(index, 1); };
  }, [keys, enabled]);
}

function isTyping(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  if (!element) return false;
  if (element.isContentEditable) return true;
  const tag = element.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || !!element.closest?.("[role=dialog] input, [contenteditable=true]");
}

/** One window listener dispatching to the registered layers (top-most first). */
export function useShortcutDispatcher(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    let pending: string | null = null;
    let timer: number | undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) return;
      if (document.querySelector("[data-cm-modal-open]")) return;
      const key = event.key === "Enter" ? "Enter" : event.key.length === 1 ? (event.shiftKey && /[a-z]/i.test(event.key) ? `Shift+${event.key.toUpperCase()}` : event.key) : event.key;
      const combo = pending ? `${pending} ${key}` : key;
      if (!pending && key === "g") {
        pending = "g";
        window.clearTimeout(timer);
        timer = window.setTimeout(() => { pending = null; }, 1200);
        return;
      }
      pending = null;
      for (let i = layers.length - 1; i >= 0; i -= 1) {
        const handler = layers[i].map[combo];
        if (handler) { event.preventDefault(); handler(event); return; }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); window.clearTimeout(timer); };
  }, [enabled]);
}

let helpOpen = false;
const helpListeners = new Set<() => void>();
function setHelp(open: boolean) { helpOpen = open; helpListeners.forEach((notify) => notify()); }
export function openShortcutHelp() { setHelp(true); }

export function ShortcutHelpDialog() {
  const open = useSyncExternalStore((notify) => { helpListeners.add(notify); return () => { helpListeners.delete(notify); }; }, () => helpOpen, () => false);
  return (
    <Dialog isOpen={open} onOpenChange={setHelp} className="max-w-2xl">
      <DialogHeader><DialogTitle>Keyboard shortcuts</DialogTitle></DialogHeader>
      <p className="mt-1 text-sm text-text-tertiary">Turn shortcuts on or off in Settings → Preferences.</p>
      <div className="mt-5 grid max-h-[65vh] gap-6 overflow-y-auto sm:grid-cols-2">
        {SHORTCUT_GROUPS.map((group) => (
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

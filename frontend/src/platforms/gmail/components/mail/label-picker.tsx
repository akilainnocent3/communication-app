"use client";

import { useState, type RefObject } from "react";
import { Dialog as AriaDialog, Popover } from "react-aria-components";
import Link from "next/link";
import { Button } from "@/components/tailgrids/core/button";
import { SearchIcon } from "@/components/ui/icons";
import type { Label, ThreadSummary } from "@/services/api/types";

type Mode = "label" | "move";

/**
 * "Label as" (tri-state checkboxes over the selection) or "Move to" (pick one label; leaves the inbox).
 * Labels belong to one mailbox, so the selection must come from a single mailbox.
 */
export function LabelPopover({ anchor, isOpen, onOpenChange, mode, labels, threads, onApply }: {
  anchor: RefObject<Element | null>; isOpen: boolean; onOpenChange: (open: boolean) => void; mode: Mode; labels: Label[]; threads: ThreadSummary[];
  onApply: (change: { add: string[]; remove: string[] } | { move: string }) => void;
}) {
  return (
    <Popover triggerRef={anchor} isOpen={isOpen} onOpenChange={onOpenChange} placement="bottom start"
      className="w-72 overflow-hidden rounded-xl border border-card-border bg-card-surface-area shadow-lg outline-none entering:animate-pop-in">
      <AriaDialog aria-label={mode === "move" ? "Move to" : "Label as"} className="outline-none">
        {isOpen && <LabelPickerBody mode={mode} labels={labels} threads={threads} onApply={(change) => { onApply(change); onOpenChange(false); }} />}
      </AriaDialog>
    </Popover>
  );
}

function LabelPickerBody({ mode, labels, threads, onApply }: { mode: Mode; labels: Label[]; threads: ThreadSummary[]; onApply: (change: { add: string[]; remove: string[] } | { move: string }) => void }) {
  const [search, setSearch] = useState("");
  const user = labels.filter((label) => label.type === "user");
  const shown = user.filter((label) => label.name.toLowerCase().includes(search.trim().toLowerCase()));
  // The body mounts each time the popover opens, so the selection's label state is captured once here.
  const [initial] = useState(() => {
    const state = new Map<string, "all" | "some" | "none">();
    for (const label of user) {
      const count = threads.filter((thread) => thread.label_ids?.includes(label.label_id)).length;
      state.set(label.label_id, count === 0 ? "none" : count === threads.length ? "all" : "some");
    }
    return state;
  });
  const [state, setState] = useState(initial);
  const changed = [...state.entries()].filter(([id, value]) => value !== initial.get(id));

  return (
    <div className="p-1.5">
      <p className="px-2.5 pt-1.5 pb-2 text-xs font-semibold tracking-wide text-text-tertiary uppercase">{mode === "move" ? "Move to" : "Label as"}</p>
      <label className="relative mx-1 mb-1.5 block">
        <span className="sr-only">Search labels</span>
        <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-icon-tertiary" />
        <input autoFocus value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search labels"
          className="h-9 w-full rounded-lg border border-card-border bg-card-surface-area pr-2 pl-8 text-sm text-text-primary placeholder:text-text-tertiary focus:border-primary-500 focus:ring-2 focus:ring-primary-500/30 focus:outline-none" />
      </label>
      <ul className="max-h-64 overflow-y-auto">
        {mode === "move" && !search && (
          <li><button type="button" onClick={() => onApply({ move: "INBOX" })} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm text-text-primary hover:bg-background-gray-secondary_alt">Inbox</button></li>
        )}
        {shown.map((label) => {
          const value = state.get(label.label_id) ?? "none";
          if (mode === "move")
            return (
              <li key={label.label_id}>
                <button type="button" onClick={() => onApply({ move: label.label_id })} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm text-text-primary hover:bg-background-gray-secondary_alt focus-visible:bg-background-gray-secondary_alt focus-visible:outline-none">
                  <span className="size-2.5 rounded-full" style={{ background: label.colour || "#9ca3af" }} />{label.name}
                </button>
              </li>
            );
          return (
            <li key={label.label_id}>
              <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-text-primary hover:bg-background-gray-secondary_alt">
                <input type="checkbox" checked={value === "all"} ref={(element) => { if (element) element.indeterminate = value === "some"; }}
                  onChange={() => setState(new Map(state).set(label.label_id, value === "all" ? "none" : "all"))}
                  className="size-4 rounded border-border-primary text-primary-500 focus:ring-primary-500" />
                <span className="size-2.5 rounded-full" style={{ background: label.colour || "#9ca3af" }} />
                <span className="truncate">{label.name}</span>
              </label>
            </li>
          );
        })}
        {!shown.length && <li className="px-2.5 py-3 text-sm text-text-tertiary">No labels{search ? ` match “${search}”` : " yet"}.</li>}
      </ul>
      <div className="mt-1.5 flex items-center justify-between gap-2 border-t border-card-border px-1.5 pt-2 pb-1">
        <Link href="/gmail/labels?new=1" className="text-sm font-medium text-primary-500 hover:underline dark:text-primary-300">Create new</Link>
        {mode === "label" && (
          <Button size="sm" isDisabled={!changed.length} onPress={() => onApply({
            add: changed.filter(([, value]) => value === "all").map(([id]) => id),
            remove: changed.filter(([, value]) => value === "none").map(([id]) => id),
          })}>Apply</Button>
        )}
      </div>
    </div>
  );
}

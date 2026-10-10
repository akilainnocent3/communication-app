"use client";

import { addDays, nextMonday, nextSaturday, set } from "date-fns";
import { formatInTimeZone, fromZonedTime, toZonedTime } from "date-fns-tz";
import { useState, type RefObject } from "react";
import { Dialog as AriaDialog, Popover } from "react-aria-components";
import { Button } from "@/components/tailgrids/core/button";
import { timezone } from "@/lib/format";

/** A wall-clock time in the user's timezone, as a UTC Date. */
function at(base: Date, hours: number) {
  const zone = timezone();
  const local = set(toZonedTime(base, zone), { hours, minutes: 0, seconds: 0, milliseconds: 0 });
  return fromZonedTime(local, zone);
}

export function snoozePresets(now = new Date()) {
  const zone = timezone();
  const localHour = Number(formatInTimeZone(now, zone, "H"));
  const presets: { label: string; date: Date }[] = [];
  if (localHour < 17) presets.push({ label: "Later today", date: at(now, 18) });
  presets.push({ label: "Tomorrow", date: at(addDays(toZonedTime(now, zone), 1), 8) });
  const day = Number(formatInTimeZone(now, zone, "i"));
  if (day < 6) presets.push({ label: "This weekend", date: at(nextSaturday(toZonedTime(now, zone)), 8) });
  presets.push({ label: "Next week", date: at(nextMonday(toZonedTime(now, zone)), 8) });
  return presets;
}

/** Snooze or schedule picker: presets in the user's timezone plus a custom date & time. */
export function TimePicker({ title, presets, onPick, onClose, custom = "Pick date & time", confirm = "Snooze" }: {
  title: string; presets: { label: string; date: Date }[]; onPick: (date: Date) => void; onClose: () => void; custom?: string; confirm?: string;
}) {
  const zone = timezone();
  const [value, setValue] = useState(() => formatInTimeZone(addDays(new Date(), 1), zone, "yyyy-MM-dd'T'08:00"));
  const [error, setError] = useState("");
  return (
    <div className="w-72 p-1.5">
      <p className="px-2.5 pt-1.5 pb-2 text-xs font-semibold tracking-wide text-text-tertiary uppercase">{title}</p>
      <ul>
        {presets.map((preset) => (
          <li key={preset.label}>
            <button type="button" onClick={() => onPick(preset.date)}
              className="flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left text-sm text-text-primary hover:bg-background-gray-secondary_alt focus-visible:bg-background-gray-secondary_alt focus-visible:outline-none">
              <span>{preset.label}</span>
              <span className="text-xs text-text-tertiary">{formatInTimeZone(preset.date, zone, "EEE, HH:mm")}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-1.5 border-t border-card-border px-2.5 pt-3 pb-2">
        <label className="block text-xs font-medium text-text-secondary" htmlFor="cm-time-custom">{custom}</label>
        <input id="cm-time-custom" type="datetime-local" value={value} onChange={(event) => { setValue(event.target.value); setError(""); }}
          className="mt-1.5 h-10 w-full rounded-lg border border-card-border bg-card-surface-area px-2.5 text-sm text-text-primary focus:border-primary-500 focus:ring-2 focus:ring-primary-500/30 focus:outline-none" />
        {error && <p role="alert" className="mt-1.5 text-xs text-error-500">{error}</p>}
        <p className="mt-1 text-[11px] text-text-tertiary">Time zone: {zone.replace("_", " ")}</p>
        <div className="mt-3 flex justify-end gap-2">
          <Button size="sm" appearance="outline" onPress={onClose}>Cancel</Button>
          <Button size="sm" onPress={() => {
            const date = fromZonedTime(value, zone);
            if (Number.isNaN(date.getTime()) || date.getTime() < Date.now() + 60_000) { setError("Choose a time in the future."); return; }
            onPick(date);
          }}>{confirm}</Button>
        </div>
      </div>
    </div>
  );
}

/** Snooze picker anchored to a button (row quick action or toolbar). */
export function SnoozePopover({ anchor, isOpen, onOpenChange, onPick }: {
  anchor: RefObject<Element | null>; isOpen: boolean; onOpenChange: (open: boolean) => void; onPick: (date: Date) => void;
}) {
  return (
    <Popover triggerRef={anchor} isOpen={isOpen} onOpenChange={onOpenChange} placement="bottom end"
      className="overflow-hidden rounded-xl border border-card-border bg-card-surface-area shadow-lg outline-none entering:animate-pop-in">
      <AriaDialog aria-label="Snooze until" className="outline-none">
        <TimePicker title="Snooze until…" presets={snoozePresets()} onPick={(date) => { onPick(date); onOpenChange(false); }} onClose={() => onOpenChange(false)} />
      </AriaDialog>
    </Popover>
  );
}

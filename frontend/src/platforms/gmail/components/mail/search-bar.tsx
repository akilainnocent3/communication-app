"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { Dialog as AriaDialog, Popover } from "react-aria-components";
import { Button } from "@/components/tailgrids/core/button";
import { CloseIcon, SearchIcon, SlidersIcon } from "@/components/ui/icons";
import { cn } from "@/utils/cn";

type Advanced = { from: string; to: string; subject: string; words: string; without: string; hasAttachment: boolean; unread: boolean; after: string; before: string; larger: string };
const EMPTY: Advanced = { from: "", to: "", subject: "", words: "", without: "", hasAttachment: false, unread: false, after: "", before: "", larger: "" };

const quote = (value: string) => (/\s/.test(value.trim()) ? `"${value.trim()}"` : value.trim());

/** Builds a Gmail-operator query from the advanced form (for people who don't know the operators). */
export function buildQuery(form: Advanced) {
  const parts: string[] = [];
  if (form.from.trim()) parts.push(`from:${quote(form.from)}`);
  if (form.to.trim()) parts.push(`to:${quote(form.to)}`);
  if (form.subject.trim()) parts.push(`subject:${quote(form.subject)}`);
  if (form.words.trim()) parts.push(form.words.trim());
  for (const word of form.without.trim().split(/\s+/).filter(Boolean)) parts.push(`-${word}`);
  if (form.hasAttachment) parts.push("has:attachment");
  if (form.unread) parts.push("is:unread");
  if (form.after) parts.push(`after:${form.after.replaceAll("-", "/")}`);
  if (form.before) parts.push(`before:${form.before.replaceAll("-", "/")}`);
  if (form.larger.trim()) parts.push(`larger:${form.larger.trim()}M`);
  return parts.join(" ");
}

export function SearchBar({ className }: { className?: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const current = params.get("q") ?? "";
  const [value, setValue] = useState(current);
  const [seen, setSeen] = useState(current);
  if (seen !== current) { setSeen(current); setValue(current); }
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Advanced>(EMPTY);
  const anchor = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  const go = (q: string) => {
    const text = q.trim();
    if (!text) return;
    router.push(`/gmail/search?q=${encodeURIComponent(text)}`);
    input.current?.blur();
  };
  const field = (key: keyof Advanced, label: string, type = "text", placeholder = "") => (
    <label className="grid grid-cols-[7rem_1fr] items-center gap-3 text-sm">
      <span className="text-text-secondary">{label}</span>
      <input type={type} value={String(form[key])} placeholder={placeholder} onChange={(event) => setForm({ ...form, [key]: event.target.value })}
        className="h-9 min-w-0 rounded-lg border border-card-border bg-card-surface-area px-2.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-primary-500 focus:ring-2 focus:ring-primary-500/30 focus:outline-none" />
    </label>
  );

  return (
    <div ref={anchor} className={cn("relative", className)}>
      <form role="search" onSubmit={(event) => { event.preventDefault(); go(value); }}
        className="flex h-11 items-center gap-1 rounded-full border border-transparent bg-background-gray-secondary_alt/80 pr-1 pl-3 transition focus-within:border-card-border focus-within:bg-card-surface-area focus-within:shadow-md dark:bg-white/5">
        <button type="submit" aria-label="Search" className="flex size-8 items-center justify-center rounded-full text-icon-tertiary hover:text-text-primary"><SearchIcon /></button>
        <label htmlFor="mail-search" className="sr-only">Search mail</label>
        <input
          ref={input}
          id="mail-search"
          type="search"
          autoComplete="off"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Escape") { setValue(current); input.current?.blur(); } }}
          placeholder="Search mail  (from:, subject:, has:attachment…)"
          className="h-full min-w-0 flex-1 border-0 bg-transparent px-1 text-sm text-text-primary placeholder:text-text-tertiary focus:ring-0 focus:outline-none [&::-webkit-search-cancel-button]:hidden"
        />
        {value && (
          <button type="button" aria-label="Clear search" onClick={() => { setValue(""); if (current) router.push("/gmail/inbox"); }} className="flex size-8 items-center justify-center rounded-full text-icon-tertiary hover:bg-background-gray-secondary hover:text-text-primary"><CloseIcon size={16} /></button>
        )}
        <button type="button" aria-label="Advanced search" aria-expanded={open} onClick={() => setOpen(true)}
          className="flex size-9 items-center justify-center rounded-full text-icon-tertiary hover:bg-background-gray-secondary hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"><SlidersIcon /></button>
      </form>
      <Popover triggerRef={anchor} isOpen={open} onOpenChange={setOpen} placement="bottom start" offset={6}
        className="w-(--trigger-width) max-w-[calc(100vw-2rem)] min-w-80 overflow-hidden rounded-xl border border-card-border bg-card-surface-area shadow-xl outline-none entering:animate-pop-in">
        <AriaDialog aria-label="Advanced search" className="outline-none">
          <form className="space-y-3 p-5" onSubmit={(event) => { event.preventDefault(); const q = buildQuery(form); setValue(q); setOpen(false); go(q); }}>
            {field("from", "From", "text", "name or email")}
            {field("to", "To")}
            {field("subject", "Subject")}
            {field("words", "Has the words")}
            {field("without", "Doesn't have")}
            {field("larger", "Larger than (MB)", "number")}
            <div className="grid grid-cols-[7rem_1fr] items-center gap-3 text-sm">
              <span className="text-text-secondary">Date within</span>
              <div className="grid min-w-0 grid-cols-2 gap-2">
                <input type="date" aria-label="After" value={form.after} onChange={(event) => setForm({ ...form, after: event.target.value })} className="h-9 min-w-0 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary focus:border-primary-500 focus:outline-none" />
                <input type="date" aria-label="Before" value={form.before} onChange={(event) => setForm({ ...form, before: event.target.value })} className="h-9 min-w-0 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary focus:border-primary-500 focus:outline-none" />
              </div>
            </div>
            <div className="flex flex-wrap gap-4 pt-1 text-sm text-text-primary">
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.hasAttachment} onChange={(event) => setForm({ ...form, hasAttachment: event.target.checked })} className="size-4 rounded text-primary-500" />Has attachment</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.unread} onChange={(event) => setForm({ ...form, unread: event.target.checked })} className="size-4 rounded text-primary-500" />Unread only</label>
            </div>
            <p className="rounded-lg bg-background-gray-secondary_alt/60 px-3 py-2 font-mono text-xs break-all text-text-secondary">{buildQuery(form) || "Your search will appear here"}</p>
            <div className="flex justify-end gap-2 pt-1">
              <Button appearance="outline" size="sm" onPress={() => setForm(EMPTY)}>Clear</Button>
              <Button type="submit" size="sm" isDisabled={!buildQuery(form)}>Search</Button>
            </div>
          </form>
        </AriaDialog>
      </Popover>
    </div>
  );
}

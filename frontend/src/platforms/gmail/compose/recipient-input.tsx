"use client";

import { useQuery } from "@tanstack/react-query";
import { useId, useRef, useState } from "react";
import { CloseIcon } from "@/components/ui/icons";
import { query, request } from "@/services/api/client";
import type { Address, ContactSuggestion } from "@/services/api/types";
import { cn } from "@/utils/cn";

const EMAIL = /^[^\s@<>()",;]+@[^\s@<>()",;]+\.[^\s@<>()",;]+$/;

/** "Name <a@b.c>" or "a@b.c" → Address. */
export function parseAddress(raw: string): Address | null {
  const text = raw.trim().replace(/[,;]$/, "");
  const match = text.match(/^(.*)<([^>]+)>$/);
  const email = (match ? match[2] : text).trim();
  if (!EMAIL.test(email)) return null;
  return { email: email.toLowerCase(), name: match ? match[1].trim().replace(/^"|"$/g, "") : "" };
}

/** To / Cc / Bcc field: chips with contact autocomplete (keyboard: ↑ ↓ Enter, Backspace removes the last chip). */
export function RecipientInput({ label, value, onChange, mailbox, autoFocus, trailing }: {
  label: string; value: Address[]; onChange: (value: Address[]) => void; mailbox?: number; autoFocus?: boolean; trailing?: React.ReactNode;
}) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const term = text.trim();
  const suggestions = useQuery({
    queryKey: ["mail", "contacts", mailbox ?? 0, term],
    queryFn: () => request<ContactSuggestion[]>(`mail/contacts/suggest/${query({ q: term, mailbox })}`),
    enabled: term.length >= 1,
    staleTime: 60_000,
  });
  const options = (suggestions.data ?? []).filter((s) => !value.some((v) => v.email === s.email)).slice(0, 8);

  const add = (address: Address) => {
    if (!value.some((item) => item.email === address.email)) onChange([...value, address]);
    setText("");
    setOpen(false);
    setActive(0);
  };
  const commit = () => {
    const parts = text.split(/[,;\s]+(?=[^>]*(?:<|$))/).map((part) => part.trim()).filter(Boolean);
    const parsed = parts.map(parseAddress);
    if (parsed.length && parsed.every(Boolean)) { onChange([...value, ...(parsed as Address[]).filter((a) => !value.some((v) => v.email === a.email))]); setText(""); return true; }
    return false;
  };

  return (
    <div className="relative flex min-h-10 items-start gap-2 border-b border-card-border py-1" onClick={() => input.current?.focus()}>
      <label htmlFor={id} className="w-10 shrink-0 pt-1.5 text-sm text-text-tertiary">{label}</label>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
        {value.map((address) => (
          <span key={address.email} title={address.email} className="inline-flex h-7 max-w-full items-center gap-1 rounded-full border border-card-border bg-background-gray-secondary_alt/60 pr-1 pl-2.5 text-xs text-text-primary">
            <span className="truncate">{address.name || address.email}</span>
            <button type="button" aria-label={`Remove ${address.email}`} onClick={(event) => { event.stopPropagation(); onChange(value.filter((item) => item.email !== address.email)); }}
              className="flex size-5 items-center justify-center rounded-full text-icon-tertiary hover:bg-background-gray-secondary hover:text-text-primary"><CloseIcon size={12} /></button>
          </span>
        ))}
        <input
          ref={input}
          id={id}
          autoFocus={autoFocus}
          role="combobox"
          aria-expanded={open && options.length > 0}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={open && options[active] ? `${id}-${active}` : undefined}
          value={text}
          autoComplete="off"
          onChange={(event) => { setText(event.target.value); setOpen(true); setActive(0); }}
          onFocus={() => setOpen(true)}
          onBlur={() => { window.setTimeout(() => setOpen(false), 120); if (text.trim()) commit(); }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" && options.length) { event.preventDefault(); setActive((active + 1) % options.length); }
            else if (event.key === "ArrowUp" && options.length) { event.preventDefault(); setActive((active - 1 + options.length) % options.length); }
            else if ((event.key === "Enter" || event.key === "Tab") && open && options[active] && term) { event.preventDefault(); add(options[active]); }
            else if ((event.key === "Enter" || event.key === "," || event.key === ";" || event.key === " ") && text.trim()) { if (commit()) event.preventDefault(); }
            else if (event.key === "Backspace" && !text && value.length) onChange(value.slice(0, -1));
            else if (event.key === "Escape") setOpen(false);
          }}
          onPaste={(event) => {
            const pasted = event.clipboardData.getData("text");
            if (/[,;\n]/.test(pasted)) {
              event.preventDefault();
              const found = pasted.split(/[,;\n]+/).map(parseAddress).filter(Boolean) as Address[];
              onChange([...value, ...found.filter((a) => !value.some((v) => v.email === a.email))]);
            }
          }}
          className="h-8 min-w-32 flex-1 border-0 bg-transparent p-0 text-sm text-text-primary placeholder:text-text-tertiary focus:ring-0 focus:outline-none"
        />
      </div>
      {trailing}
      {open && term && options.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className="absolute top-full right-0 left-12 z-50 mt-1 max-h-64 overflow-y-auto rounded-xl border border-card-border bg-card-surface-area p-1 shadow-lg">
          {options.map((option, index) => (
            <li key={option.email} id={`${id}-${index}`} role="option" aria-selected={index === active}
              onMouseDown={(event) => { event.preventDefault(); add(option); }}
              className={cn("flex cursor-pointer flex-col rounded-lg px-3 py-2 text-sm", index === active ? "bg-primary-500/10" : "hover:bg-background-gray-secondary_alt")}>
              <span className="truncate font-medium text-text-primary">{option.name || option.email}</span>
              {option.name && <span className="truncate text-xs text-text-tertiary">{option.email}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

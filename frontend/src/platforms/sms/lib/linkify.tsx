"use client";

import { useState, type ReactNode } from "react";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { m } from "@/i18n";

const URL_RE = /\b((?:https?:\/\/|www\.)[^\s<>"']+[^\s<>"'.,;:!?)\]])/gi;

/**
 * Message text is rendered as text only (never HTML). URLs become links that first show a "you're leaving" warning
 * and open with rel="noopener noreferrer". No link previews: fetching them would leak the URL to third parties.
 */
export function LinkifiedText({ text }: { text: string }) {
  const [target, setTarget] = useState<string | null>(null);
  const parts: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(URL_RE)) {
    const start = match.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    const raw = match[0];
    const href = raw.startsWith("http") ? raw : `https://${raw}`;
    parts.push(
      <a key={start} href={href} onClick={(event) => { event.preventDefault(); setTarget(href); }} rel="noopener noreferrer" target="_blank"
        className="break-all underline decoration-current/40 underline-offset-2 hover:decoration-current">{raw}</a>,
    );
    last = start + raw.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  let host = "";
  try { host = target ? new URL(target).host : ""; } catch { host = target ?? ""; }
  return (
    <>
      {parts}
      <Dialog isOpen={!!target} onOpenChange={(open) => !open && setTarget(null)} role="alertdialog" className="max-w-md">
        <DialogHeader><DialogTitle>{m.sms.chat.externalLink}</DialogTitle></DialogHeader>
        <p className="mt-2 text-sm text-text-secondary">{m.sms.chat.externalLinkBody(host)}</p>
        <p className="mt-2 rounded-lg bg-background-gray-secondary_alt px-3 py-2 font-mono text-xs break-all text-text-primary">{target}</p>
        <div className="mt-6 flex justify-end gap-2">
          <Button appearance="outline" onPress={() => setTarget(null)}>{m.common.cancel}</Button>
          <Button onPress={() => { if (target) window.open(target, "_blank", "noopener,noreferrer"); setTarget(null); }}>{m.sms.chat.openLink}</Button>
        </div>
      </Dialog>
    </>
  );
}

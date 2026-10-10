"use client";

import { useState } from "react";
import { Dialog } from "@/components/tailgrids/core/dialog";
import { DownloadIcon, EyeIcon, FileIcon, ImageIcon, PdfIcon } from "@/components/ui/icons";
import { bytes } from "@/lib/format";
import type { Attachment } from "@/services/api/types";

const previewable = (type: string) => type.startsWith("image/") || type === "application/pdf";
const iconFor = (type: string) => (type.startsWith("image/") ? <ImageIcon /> : type === "application/pdf" ? <PdfIcon /> : <FileIcon />);
const download = (url: string) => `${url}${url.includes("?") ? "&" : "?"}download=1`;
/** Attachments are CSP-sandboxed by default; Chrome only renders a PDF when the in-app preview opts out of that. */
const pdfPreview = (url: string) => `${url}${url.includes("?") ? "&" : "?"}preview=1`;

/** Attachment cards under a message: preview (image / PDF lightbox) and download through the permission-checked API. */
export function Attachments({ items }: { items: Attachment[] }) {
  const [preview, setPreview] = useState<Attachment | null>(null);
  if (!items.length) return null;
  return (
    <div className="mt-4 border-t border-card-border pt-3">
      <p className="mb-2 text-xs font-medium text-text-tertiary">{items.length} attachment{items.length > 1 ? "s" : ""}</p>
      <ul className="flex flex-wrap gap-2.5">
        {items.map((item) => (
          <li key={item.id} className="group relative w-52 overflow-hidden rounded-xl border border-card-border bg-card-surface-area transition hover:border-primary-500/40 hover:shadow-sm">
            <button type="button" onClick={() => previewable(item.mime_type) && setPreview(item)} disabled={!previewable(item.mime_type)}
              className="flex h-24 w-full items-center justify-center overflow-hidden bg-background-gray-secondary_alt/60 text-icon-tertiary disabled:cursor-default [&_svg]:size-8" aria-label={`Preview ${item.filename}`}>
              {item.mime_type.startsWith("image/") ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={item.url} alt="" loading="lazy" className="size-full object-cover" />
              ) : iconFor(item.mime_type)}
            </button>
            <div className="flex items-center gap-2 px-3 py-2">
              <span className="shrink-0 text-icon-tertiary [&_svg]:size-4">{iconFor(item.mime_type)}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-medium text-text-primary" title={item.filename}>{item.filename}</span>
                <span className="block text-[11px] text-text-tertiary">{bytes(item.size)}</span>
              </span>
              <a href={download(item.url)} aria-label={`Download ${item.filename}`} title="Download"
                className="flex size-8 shrink-0 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
                <DownloadIcon size={16} />
              </a>
            </div>
          </li>
        ))}
      </ul>
      <Dialog isOpen={!!preview} onOpenChange={(open) => !open && setPreview(null)} className="flex h-[min(88vh,900px)] max-w-5xl flex-col p-0">
        {preview && (
          <>
            <div className="flex items-center gap-3 border-b border-card-border py-3 pr-14 pl-5">
              <EyeIcon className="text-icon-tertiary" />
              <p className="min-w-0 flex-1 truncate text-sm font-medium text-text-primary">{preview.filename}</p>
              <a href={download(preview.url)} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-card-border px-3 text-sm font-medium text-text-primary hover:bg-background-gray-secondary_alt"><DownloadIcon size={16} />Download</a>
            </div>
            <div className="flex min-h-0 flex-1 items-center justify-center bg-background-gray-secondary_alt/50 p-3">
              {preview.mime_type.startsWith("image/") ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={preview.url} alt={preview.filename} className="max-h-full max-w-full rounded-lg object-contain shadow" />
              ) : (
                <iframe src={pdfPreview(preview.url)} title={preview.filename} className="size-full rounded-lg border-0 bg-white" />
              )}
            </div>
          </>
        )}
      </Dialog>
    </div>
  );
}

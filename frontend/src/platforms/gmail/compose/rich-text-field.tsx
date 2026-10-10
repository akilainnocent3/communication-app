"use client";

import { ComposeEditorContent, EditorToolbar, useComposeEditor } from "./editor";

/** The compose editor as a form field (templates, signatures, vacation reply). Remount with `key` to load new content. */
export function RichTextField({ label, initial, onChange, placeholder = "", minHeight = 160 }: {
  label: string; initial: string; onChange: (html: string) => void; placeholder?: string; minHeight?: number;
}) {
  const editor = useComposeEditor({ initial, placeholder, onChange: (html) => onChange(html) });
  return (
    <div className="min-w-0 text-sm">
      <p className="mb-2 font-medium text-text-primary">{label}</p>
      <div className="rounded-lg border border-card-border bg-input-background focus-within:border-input-primary-focus-border focus-within:ring-4 focus-within:ring-input-primary-focus-border/20">
        <EditorToolbar editor={editor} className="border-b border-card-border px-1.5 py-1" />
        <ComposeEditorContent editor={editor} className={minHeight > 200 ? "px-3 [&_.cm-editor]:min-h-64" : "px-3 [&_.cm-editor]:min-h-36"} />
      </div>
    </div>
  );
}

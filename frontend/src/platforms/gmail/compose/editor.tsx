"use client";

import { Color, TextStyle } from "@tiptap/extension-text-style";
import { Placeholder } from "@tiptap/extensions";
import { EditorContent, useEditor, useEditorState, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { cn } from "@/utils/cn";

const COLOURS = ["#111827", "#6b7280", "#dc2626", "#ea580c", "#ca8a04", "#16a34a", "#2563eb", "#7c3aed"];

function ToolbarButton({ label, active, onClick, children }: { label: string; active?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} aria-pressed={active} onMouseDown={(event) => event.preventDefault()} onClick={onClick}
      className={cn("flex size-8 items-center justify-center rounded-md text-sm text-text-secondary transition-colors hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none",
        active && "bg-primary-500/10 text-primary-600 dark:text-primary-300")}>
      {children}
    </button>
  );
}

/** Formatting bar: bold, italic, underline, lists, quote, link, text colour, clear formatting. */
export function EditorToolbar({ editor, className }: { editor: Editor | null; className?: string }) {
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => e ? ({
      bold: e.isActive("bold"), italic: e.isActive("italic"), underline: e.isActive("underline"), bullet: e.isActive("bulletList"),
      ordered: e.isActive("orderedList"), quote: e.isActive("blockquote"), link: e.isActive("link"), colour: e.getAttributes("textStyle").color as string | undefined,
    }) : null,
  });
  if (!editor || !state) return null;
  const chain = () => editor.chain().focus();
  return (
    <div role="toolbar" aria-label="Formatting" className={cn("flex flex-wrap items-center gap-0.5", className)}>
      <ToolbarButton label="Bold (Ctrl+B)" active={state.bold} onClick={() => chain().toggleBold().run()}><b>B</b></ToolbarButton>
      <ToolbarButton label="Italic (Ctrl+I)" active={state.italic} onClick={() => chain().toggleItalic().run()}><i className="font-serif">I</i></ToolbarButton>
      <ToolbarButton label="Underline (Ctrl+U)" active={state.underline} onClick={() => chain().toggleUnderline().run()}><u>U</u></ToolbarButton>
      <span aria-hidden="true" className="mx-0.5 h-5 w-px bg-card-border" />
      <ToolbarButton label="Bulleted list" active={state.bullet} onClick={() => chain().toggleBulletList().run()}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M9 6h11M9 12h11M9 18h11" /><circle cx="4.5" cy="6" r="1" fill="currentColor" /><circle cx="4.5" cy="12" r="1" fill="currentColor" /><circle cx="4.5" cy="18" r="1" fill="currentColor" /></svg>
      </ToolbarButton>
      <ToolbarButton label="Numbered list" active={state.ordered} onClick={() => chain().toggleOrderedList().run()}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M10 6h10M10 12h10M10 18h10M4 5h1.5v4M4 9h3M4 15.5c0-1 2.5-1.2 2.5.2 0 1-2.5 2.3-2.5 3.3h2.7" /></svg>
      </ToolbarButton>
      <ToolbarButton label="Quote" active={state.quote} onClick={() => chain().toggleBlockquote().run()}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7.2 17c-1.8 0-3.2-1.5-3.2-3.6C4 9.6 6.7 7 9.8 6.5l.4 1.4C8.3 8.6 7.2 9.9 7 11.3c1.6-.2 3 .9 3 2.6S8.8 17 7.2 17zm8.5 0c-1.8 0-3.2-1.5-3.2-3.6 0-3.8 2.7-6.4 5.8-6.9l.4 1.4c-1.9.7-3 2-3.2 3.4 1.6-.2 3 .9 3 2.6s-1.2 3.1-2.8 3.1z" /></svg>
      </ToolbarButton>
      <ToolbarButton label={state.link ? "Remove link" : "Insert link"} active={state.link} onClick={() => {
        if (state.link) { chain().unsetLink().run(); return; }
        const url = window.prompt("Link address (https://…)", "https://");
        if (!url || url === "https://") return;
        const safe = /^(https?:|mailto:|tel:)/i.test(url) ? url : `https://${url}`;
        if (editor.state.selection.empty) chain().insertContent(`<a href="${safe.replace(/"/g, "%22")}">${safe.replace(/[<>&]/g, "")}</a>`).run();
        else chain().setLink({ href: safe }).run();
      }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></svg>
      </ToolbarButton>
      <label className="relative flex size-8 cursor-pointer items-center justify-center rounded-md hover:bg-background-gray-secondary_alt" title="Text colour">
        <span className="sr-only">Text colour</span>
        <span aria-hidden="true" className="flex flex-col items-center text-sm leading-none font-semibold text-text-secondary">A<span className="mt-0.5 h-1 w-4 rounded-full" style={{ background: state.colour || "#111827" }} /></span>
        <select className="absolute inset-0 cursor-pointer opacity-0" value={state.colour || ""} onChange={(event) => (event.target.value ? chain().setColor(event.target.value).run() : chain().unsetColor().run())}>
          <option value="">Default</option>
          {COLOURS.map((colour) => <option key={colour} value={colour}>{colour}</option>)}
        </select>
      </label>
      <ToolbarButton label="Clear formatting" onClick={() => chain().clearNodes().unsetAllMarks().run()}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><path d="M6 5h12M12 5l-3 14M4 20 20 4" /></svg>
      </ToolbarButton>
    </div>
  );
}

export function useComposeEditor({ initial, placeholder, onChange, onPasteFiles }: {
  initial: string; placeholder: string; onChange: (html: string, text: string) => void; onPasteFiles?: (files: File[]) => void;
}) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({ heading: false, codeBlock: false, link: { openOnClick: false, autolink: true, defaultProtocol: "https", HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" } } }),
      TextStyle,
      Color,
      Placeholder.configure({ placeholder }),
    ],
    content: initial,
    editorProps: {
      attributes: { class: "cm-editor prose-email min-h-full px-1 py-2 text-sm text-text-primary outline-none", "aria-label": "Message body", role: "textbox", "aria-multiline": "true" },
      handlePaste: (_view, event) => {
        const files = Array.from(event.clipboardData?.files ?? []);
        if (files.length && onPasteFiles) { onPasteFiles(files); return true; }
        return false;
      },
    },
    onUpdate: ({ editor: e }) => onChange(e.getHTML(), e.getText()),
  });
  return editor;
}

export function ComposeEditorContent({ editor, className }: { editor: Editor | null; className?: string }) {
  return <EditorContent editor={editor} className={className} />;
}

"use client";

import DOMPurify from "dompurify";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";
import { DotsIcon } from "@/components/ui/icons";

/**
 * Email HTML is sanitised by the server (nh3) and again here (DOMPurify), then rendered in a sandboxed iframe
 * with a CSP that forbids scripts, frames, forms and every network fetch except images (and those only when the
 * user chose to show them). `allow-same-origin` (without `allow-scripts`) lets the parent size the frame and fold
 * quoted text; nothing inside the frame can run. See docs/security.md.
 */
function documentFor(html: string, dark: boolean, imagesAllowed: boolean) {
  const clean = DOMPurify.sanitize(html, {
    FORBID_TAGS: ["style", "script", "iframe", "object", "embed", "form", "input", "button", "textarea", "select", "link", "meta", "base", "svg", "math"],
    FORBID_ATTR: ["srcset", "action", "formaction", "ping", "background"],
    ALLOW_DATA_ATTR: true,
    ADD_ATTR: ["target"],
  });
  const csp = `default-src 'none'; img-src data: ${imagesAllowed ? "https: http:" : ""}; style-src 'unsafe-inline'; font-src data:; base-uri 'none'; form-action 'none'`;
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${csp}"><meta name="referrer" content="no-referrer"><base target="_blank"><style>
  :root{color-scheme:${dark ? "dark" : "light"}}
  html,body{margin:0;padding:0;overflow-y:hidden}
  body{font:14px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:${dark ? "#e5e7eb" : "#1f2937"};background:transparent;word-wrap:break-word;overflow-wrap:anywhere}
  img{max-width:100%;height:auto}
  img[data-cm-src]{display:inline-block;min-width:24px;min-height:16px;background:${dark ? "#1f2937" : "#f3f4f6"};border-radius:4px}
  table{max-width:100%}
  a{color:${dark ? "#91aeff" : "#2237ee"}}
  a[data-cm-mismatch]{background:rgba(234,179,8,.18);border-radius:3px;outline:1px dashed #eab308;outline-offset:1px}
  blockquote{margin:8px 0;padding-left:12px;border-left:3px solid ${dark ? "#374151" : "#e5e7eb"};color:${dark ? "#9ca3af" : "#6b7280"}}
  pre{white-space:pre-wrap}
  .cm-quote-hidden{display:none!important}
  </style></head><body>${clean}</body></html>`;
}

/** Hides the trailing quoted reply (last top-level blockquote and its "On … wrote:" line). */
function foldQuote(doc: Document, show: boolean) {
  const body = doc.body;
  if (!body) return false;
  const blocks = Array.from(body.querySelectorAll(":scope > blockquote, :scope > div > blockquote"));
  const last = blocks[blocks.length - 1] as HTMLElement | undefined;
  if (!last) return false;
  // Only fold when nothing but whitespace follows the quote (a real trailing reply).
  let node: Node | null = last;
  while (node && node !== body) {
    let sibling = node.nextSibling;
    while (sibling) { if ((sibling.textContent ?? "").trim()) return false; sibling = sibling.nextSibling; }
    node = node.parentNode;
  }
  const targets: HTMLElement[] = [last];
  const previous = last.previousElementSibling as HTMLElement | null;
  if (previous && /^on .{4,200} wrote:?$/i.test((previous.textContent ?? "").trim())) targets.push(previous);
  for (const element of targets) element.classList.toggle("cm-quote-hidden", !show);
  return true;
}

export function EmailFrame({ html, title, imagesAllowed }: { html: string; title: string; imagesAllowed: boolean }) {
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  const frame = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(48);
  const [hasQuote, setHasQuote] = useState(false);
  const [showQuote, setShowQuote] = useState(false);
  const srcDoc = useMemo(() => documentFor(html, dark, imagesAllowed), [html, dark, imagesAllowed]);

  useEffect(() => {
    const element = frame.current;
    if (!element) return;
    let observer: ResizeObserver | undefined;
    const measure = () => {
      const doc = element.contentDocument;
      if (doc?.documentElement) setHeight(Math.max(24, Math.ceil(doc.documentElement.scrollHeight)));
    };
    const onLoad = () => {
      const doc = element.contentDocument;
      if (!doc) return;
      setHasQuote(foldQuote(doc, showQuote));
      measure();
      // The observer lives in this window, so it also catches late image loads. Listeners added inside the frame
      // would never run: the sandbox has no allow-scripts (Chrome logs "Blocked script execution").
      observer = new ResizeObserver(measure);
      observer.observe(doc.body);
    };
    element.addEventListener("load", onLoad);
    if (element.contentDocument?.readyState === "complete") onLoad();
    return () => { element.removeEventListener("load", onLoad); observer?.disconnect(); };
    // showQuote is applied by the effect below without reloading the frame.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [srcDoc]);

  useEffect(() => {
    const doc = frame.current?.contentDocument;
    if (doc && hasQuote) {
      foldQuote(doc, showQuote);
      setHeight(Math.max(24, Math.ceil(doc.documentElement.scrollHeight)));
    }
  }, [showQuote, hasQuote]);

  return (
    <div>
      <iframe
        ref={frame}
        title={title}
        srcDoc={srcDoc}
        sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
        referrerPolicy="no-referrer"
        style={{ height }}
        className="block w-full border-0 bg-transparent"
      />
      {hasQuote && (
        <button type="button" onClick={() => setShowQuote(!showQuote)} aria-expanded={showQuote}
          aria-label={showQuote ? "Hide quoted text" : "Show quoted text"} title={showQuote ? "Hide quoted text" : "Show quoted text"}
          className="mt-1 flex h-5 items-center rounded-md bg-background-gray-secondary_alt px-2 text-icon-secondary hover:bg-background-gray-secondary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
          <DotsIcon size={16} />
        </button>
      )}
    </div>
  );
}

/** Same pipeline for printing: one document with every message, printed from a hidden frame. */
export function printThread(subject: string, parts: { header: string; html: string }[]) {
  const body = parts.map((part) => `<section style="border-top:1px solid #e5e7eb;padding:12px 0">${DOMPurify.sanitize(part.header)}${DOMPurify.sanitize(part.html)}</section>`).join("");
  const doc = `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'"><title>${DOMPurify.sanitize(subject)}</title><style>body{font:13px/1.5 Arial,sans-serif;color:#111;margin:24px}h1{font-size:18px}img{max-width:100%}</style></head><body><h1>${DOMPurify.sanitize(subject)}</h1>${body}</body></html>`;
  const frame = document.createElement("iframe");
  frame.setAttribute("sandbox", "allow-same-origin allow-modals");
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  frame.srcdoc = doc;
  frame.onload = () => { frame.contentWindow?.print(); window.setTimeout(() => frame.remove(), 1000); };
  document.body.appendChild(frame);
}

"use client";

import { useMediaQuery } from "@/hooks/use-media-query";
import { CloseIcon, ExpandIcon, MinusIcon } from "@/components/ui/icons";
import { cn } from "@/utils/cn";
import { ComposeFields, useComposeForm } from "./compose-form";
import { closeCompose, updateCompose, useComposeWindows, type ComposeWindow } from "./store";

const WIDTH = 540;

function Window({ win, index, mobile }: { win: ComposeWindow; index: number; mobile: boolean }) {
  const c = useComposeForm(win, () => closeCompose(win.key));
  const title = c.subject.trim() || (win.mode === "forward" ? "Forward" : win.mode === "new" ? "New message" : "Reply");
  const full = mobile || win.maximized;
  const header = (
    <div className={cn("flex h-10 shrink-0 cursor-pointer items-center gap-2 bg-[#1f2937] pr-1.5 pl-4 text-white dark:bg-[#0b1120]", !full && "rounded-t-xl")}
      onClick={() => !mobile && updateCompose(win.key, { minimized: !win.minimized })}>
      <h2 className="min-w-0 flex-1 truncate text-sm font-medium">{title}</h2>
      {!mobile && (
        <>
          <button type="button" aria-label={win.minimized ? "Restore" : "Minimise"} onClick={(event) => { event.stopPropagation(); updateCompose(win.key, { minimized: !win.minimized }); }} className="flex size-8 items-center justify-center rounded-md text-white/80 hover:bg-white/10 hover:text-white"><MinusIcon size={16} /></button>
          <button type="button" aria-label={win.maximized ? "Exit full screen" : "Full screen"} onClick={(event) => { event.stopPropagation(); updateCompose(win.key, { maximized: !win.maximized, minimized: false }); }} className="flex size-8 items-center justify-center rounded-md text-white/80 hover:bg-white/10 hover:text-white"><ExpandIcon size={16} /></button>
        </>
      )}
      <button type="button" aria-label="Save and close" onClick={(event) => { event.stopPropagation(); c.close(); }} className="flex size-8 items-center justify-center rounded-md text-white/80 hover:bg-white/10 hover:text-white"><CloseIcon size={16} /></button>
    </div>
  );
  if (full)
    return (
      <div className={cn("fixed z-[70] flex flex-col overflow-hidden bg-card-surface-area shadow-2xl", mobile ? "inset-0" : "inset-[6vh_8vw] rounded-xl border border-card-border")} role="dialog" aria-label={title} aria-modal={mobile}>
        {header}
        <div className="flex min-h-0 flex-1 flex-col"><ComposeFields c={c} variant="window" /></div>
      </div>
    );
  return (
    <div role="dialog" aria-label={title}
      style={{ right: 16 + index * (WIDTH + 12), width: win.minimized ? 280 : WIDTH }}
      className={cn("fixed bottom-0 z-[70] flex flex-col overflow-hidden rounded-t-xl border border-b-0 border-card-border bg-card-surface-area shadow-[0_8px_30px_rgba(0,0,0,0.22)] transition-[height,width] duration-200", win.minimized ? "h-10" : "h-[min(580px,calc(100vh-5rem))]")}>
      {header}
      <div className={cn("flex min-h-0 flex-1 flex-col", win.minimized && "hidden")}><ComposeFields c={c} variant="window" /></div>
    </div>
  );
}

/** Floating compose windows (bottom-right, stacking; full screen on phones). */
export function ComposeManager() {
  const windows = useComposeWindows();
  const mobile = !useMediaQuery("(min-width: 768px)");
  const shown = mobile ? windows.slice(-1) : windows;
  return (
    <>
      {[...shown].reverse().map((win, index) => <Window key={win.key} win={win} index={index} mobile={mobile} />)}
    </>
  );
}

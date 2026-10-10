"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/tailgrids/core/dropdown";
import { Skeleton } from "@/components/tailgrids/core/skeleton";
import {
  ArchiveIcon, ArrowLeftIcon, ChevronLeftIcon, ChevronRightIcon, CloseIcon, DotsVerticalIcon, ExpandIcon, ForwardIcon, ImportantIcon, InboxIcon,
  MuteIcon, PrinterIcon, ReplyAllIcon, ReplyIcon, SnoozeIcon, SpamIcon, StarIcon, TagIcon, TrashIcon, UnreadIcon,
} from "@/components/ui/icons";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RequestState } from "@/components/ui/request-state";
import { usePageTitle } from "@/components/shell/trail";
import { fullDate } from "@/lib/format";
import { errorMessage, mutate, request } from "@/services/api/client";
import type { ActionRequest, Message, ThreadDetail } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { useThreadActions } from "../../api/actions";
import { mailKeys } from "../../api/keys";
import { threadPath, useLabels, useThread } from "../../api/queries";
import { InlineReply } from "../../compose/compose-form";
import { defaultReplyMode, replyInit } from "../../compose/reply";
import { openCompose, type ComposeInit } from "../../compose/store";
import { useShortcuts } from "../../shortcuts";
import { InternalPanel } from "./internal-panel";
import { LabelPopover } from "./label-picker";
import { MessageCard, type MessageActions } from "./message-card";
import { displayName } from "./participants";
import { SnoozePopover } from "./snooze-picker";
import { printThread } from "./email-frame";

const REMOVES = new Set<ActionRequest["action"]>(["archive", "trash", "spam", "not_spam", "delete_forever", "move_to_label", "snooze", "mute", "untrash", "move_to_inbox"]);

function ToolButton({ label, onPress, children, className, disabled, buttonRef }: { label: string; onPress: () => void; children: React.ReactNode; className?: string; disabled?: boolean; buttonRef?: React.Ref<HTMLButtonElement> }) {
  return (
    <button ref={buttonRef} type="button" aria-label={label} title={label} onClick={onPress} disabled={disabled}
      className={cn("flex size-9 shrink-0 items-center justify-center rounded-full text-icon-secondary transition-colors hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none disabled:opacity-40 [&_svg]:size-[18px]", className)}>
      {children}
    </button>
  );
}

export function ThreadSkeleton() {
  return (
    <div role="status" aria-label="Loading conversation" className="px-4 py-5 sm:px-6">
      <Skeleton className="h-6 w-2/3" />
      <div className="mt-6 flex gap-3"><Skeleton className="size-10 rounded-full" /><div className="flex-1 space-y-2"><Skeleton className="h-3.5 w-40" /><Skeleton className="h-3 w-56" /></div></div>
      <div className="mt-6 space-y-2.5 sm:pl-[52px]">{[90, 96, 80, 60, 88].map((w, i) => <Skeleton key={i} className="h-3" style={{ width: `${w}%` }} />)}</div>
    </div>
  );
}

export type ThreadViewProps = {
  threadId: number;
  /** "pane" inside the split view, "page" full width (mobile / no split). */
  layout: "pane" | "page";
  label?: string;
  position?: { index: number; total: number | null };
  onBack: () => void;
  onPrev?: () => void;
  onNext?: () => void;
  /** Called after an action removed the thread from the current list (open the next one). */
  onRemoved: () => void;
};

export function ThreadView({ threadId, layout, label, position, onBack, onPrev, onNext, onRemoved }: ThreadViewProps) {
  const thread = useThread(threadId);
  const client = useQueryClient();
  const { run } = useThreadActions();
  const [imagesFor, setImagesFor] = useState<Set<number>>(new Set());
  const images = useQuery({
    queryKey: ["mail", "thread-images", threadId],
    queryFn: () => request<ThreadDetail>(`${threadPath(threadId, true)}&images=1`),
    enabled: imagesFor.size > 0,
    staleTime: 5 * 60_000,
  });
  const data = thread.data;
  usePageTitle(data ? (data.subject || "(no subject)") : null);

  const [reply, setReply] = useState<ComposeInit | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [seenThread, setSeenThread] = useState<number | null>(null);
  if (data && seenThread !== data.id) {
    setSeenThread(data.id);
    const last = data.messages[data.messages.length - 1];
    setExpanded(new Set(data.messages.filter((m) => m.is_unread || m.id === last?.id).map((m) => m.id)));
    setReply(null);
    setShowAll(false);
  }
  const [snoozeOpen, setSnoozeOpen] = useState(false);
  const [labelMode, setLabelMode] = useState<"label" | "move" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const snoozeRef = useRef<HTMLButtonElement>(null);
  const labelRef = useRef<HTMLButtonElement>(null);
  const moveRef = useRef<HTMLButtonElement>(null);
  const labels = useLabels(data?.mailbox.id);
  const replyRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (reply) replyRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [reply]);

  const act = async (req: Omit<ActionRequest, "thread_ids">) => {
    const removes = REMOVES.has(req.action) && !(req.action === "trash" && label === "TRASH") && !(req.action === "spam" && label === "SPAM");
    if (removes) onRemoved();
    await run({ ...req, thread_ids: [threadId] });
  };

  const messages = data?.messages ?? [];
  const lastMessage = messages[messages.length - 1];
  const perms = data?.permissions;
  const caps = data?.capabilities;
  const inTrash = data?.label_ids?.includes("TRASH");
  const inSpam = data?.label_ids?.includes("SPAM");
  const inInbox = data?.label_ids?.includes("INBOX");

  const startReply = (message: Message, mode: "reply" | "reply_all" | "forward") => {
    if (!data || !perms?.send) return;
    setReply(replyInit(data, message, mode));
  };

  const messageActions: MessageActions = useMemo(() => ({
    onReply: (message, mode) => startReply(message, mode),
    onShowImages: async (message, always) => {
      if (always && message.from_addr) {
        try { await mutate("mail/trusted-senders/", "POST", { email: message.from_addr.email }); toast.success(`Images from ${message.from_addr.email} will always show.`); }
        catch (error) { toast.error(errorMessage(error)); }
      }
      setImagesFor((set) => new Set(set).add(message.id));
    },
    onUnsubscribe: async (message) => {
      try {
        const result = await mutate<{ method: string; done: boolean; target?: string }>(`mail/messages/${message.id}/unsubscribe/`, "POST");
        if (result.done) toast.success("Unsubscribed. You should stop getting these messages.");
        else if (result.target) { window.open(result.target, "_blank", "noopener,noreferrer"); toast("Finish unsubscribing in the page that opened."); }
      } catch (error) { toast.error(errorMessage(error)); }
    },
    onShowOriginal: (message) => window.open(`/api/v1/mail/messages/${message.id}/raw/`, "_blank", "noopener,noreferrer"),
    // startReply closes over the current thread data only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [data]);

  useShortcuts({
    u: onBack,
    Escape: onBack,
    r: () => lastMessage && startReply(lastMessage, "reply"),
    a: () => lastMessage && startReply(lastMessage, "reply_all"),
    f: () => lastMessage && startReply(lastMessage, "forward"),
    e: () => perms?.send && act({ action: "archive" }),
    "#": () => perms?.delete && act({ action: "trash" }),
    "!": () => perms?.send && act({ action: "spam" }),
    s: () => act({ action: data?.is_starred ? "unstar" : "star" }),
    "Shift+U": () => { act({ action: "unread" }); onBack(); },
    "Shift+I": () => act({ action: "read" }),
    l: () => perms?.send && caps?.labels && setLabelMode("label"),
    v: () => perms?.send && caps?.labels && setLabelMode("move"),
    b: () => perms?.send && setSnoozeOpen(true),
  }, !!data);

  if (thread.isPending) return <ThreadSkeleton />;
  if (thread.error || !data)
    return <div className="p-6"><RequestState loading={false} error={errorMessage(thread.error)} onRetry={() => thread.refetch()} /></div>;

  const imageData = images.data;
  const shownMessages = messages.map((message) => {
    if (!imagesFor.has(message.id)) return message;
    return imageData?.messages.find((m) => m.id === message.id) ?? message;
  });
  const collapsedMiddle = !showAll && messages.length > 4 ? shownMessages.slice(1, -2).filter((m) => !expanded.has(m.id)) : [];
  const hidden = new Set(collapsedMiddle.length > 1 ? collapsedMiddle.map((m) => m.id) : []);
  const userLabels = data.labels ?? [];

  return (
    <div className="flex min-h-full flex-col" data-thread-view={data.id}>
      <div className={cn("sticky top-0 z-20 flex h-12 shrink-0 items-center gap-0.5 border-b border-card-border bg-card-surface-area/95 px-2 backdrop-blur sm:px-3", layout === "page" && "xl:px-4")}>
        <ToolButton label={layout === "pane" ? "Close (u)" : "Back to list (u)"} onPress={onBack}>{layout === "pane" ? <CloseIcon /> : <ArrowLeftIcon />}</ToolButton>
        <span aria-hidden="true" className="mx-1 h-5 w-px bg-card-border" />
        {perms?.send && !inTrash && !inSpam && inInbox && <ToolButton label="Archive (e)" onPress={() => act({ action: "archive" })}><ArchiveIcon /></ToolButton>}
        {perms?.send && !inInbox && <ToolButton label={inSpam ? "Not spam" : "Move to Inbox"} onPress={() => act({ action: inSpam ? "not_spam" : inTrash ? "untrash" : "move_to_inbox" })}><InboxIcon /></ToolButton>}
        {perms?.send && !inSpam && !inTrash && <ToolButton label="Report spam (!)" onPress={() => act({ action: "spam" })}><SpamIcon /></ToolButton>}
        {perms?.delete && (inTrash || inSpam
          ? <ToolButton label="Delete forever" onPress={() => setConfirmDelete(true)} className="text-error-500"><TrashIcon /></ToolButton>
          : <ToolButton label="Delete (#)" onPress={() => act({ action: "trash" })}><TrashIcon /></ToolButton>)}
        <span aria-hidden="true" className="mx-1 hidden h-5 w-px bg-card-border sm:block" />
        <ToolButton label="Mark as unread (Shift+U)" onPress={() => { act({ action: "unread" }); onBack(); }}><UnreadIcon /></ToolButton>
        {perms?.send && <ToolButton label="Snooze (b)" onPress={() => setSnoozeOpen(true)} buttonRef={snoozeRef}><SnoozeIcon /></ToolButton>}
        {perms?.send && caps?.labels && <ToolButton label="Move to (v)" onPress={() => setLabelMode("move")} buttonRef={moveRef} className="max-sm:hidden"><ExpandIcon /></ToolButton>}
        {perms?.send && caps?.labels && <ToolButton label="Labels (l)" onPress={() => setLabelMode("label")} buttonRef={labelRef}><TagIcon /></ToolButton>}
        <DropdownMenu>
          <DropdownMenuTrigger aria-label="More actions" className="flex size-9 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500"><DotsVerticalIcon /></DropdownMenuTrigger>
          <DropdownMenuContent placement="bottom start" className="w-60 p-1.5">
            {caps?.important && <DropdownMenuItem onAction={() => act({ action: data.is_important ? "not_important" : "important" })} className="px-3 py-2"><ImportantIcon />{data.is_important ? "Mark as not important" : "Mark as important"}</DropdownMenuItem>}
            {perms?.send && <DropdownMenuItem onAction={() => act({ action: data.is_muted ? "unmute" : "mute" })} className="px-3 py-2"><MuteIcon />{data.is_muted ? "Unmute" : "Mute"}</DropdownMenuItem>}
            {data.snoozed_until && perms?.send && <DropdownMenuItem onAction={() => act({ action: "unsnooze" })} className="px-3 py-2"><SnoozeIcon />Unsnooze</DropdownMenuItem>}
            <DropdownMenuItem onAction={() => printThread(data.subject || "(no subject)", shownMessages.map((m) => ({ header: `<p><b>${displayName(m.from_addr)}</b> · ${fullDate(m.date)}</p>`, html: m.body_html })))} className="px-3 py-2"><PrinterIcon />Print all</DropdownMenuItem>
            {perms?.delete && !inTrash && !inSpam && (<><DropdownMenuSeparator className="my-1" /><DropdownMenuItem onAction={() => setConfirmDelete(true)} className="px-3 py-2 text-error-500"><TrashIcon />Delete forever</DropdownMenuItem></>)}
          </DropdownMenuContent>
        </DropdownMenu>
        <div className="ml-auto flex items-center gap-0.5">
          {position && <span className="hidden text-xs text-text-tertiary tabular-nums sm:inline">{position.index + 1} of {position.total ?? "many"}</span>}
          <ToolButton label="Newer (k)" onPress={() => onPrev?.()} disabled={!onPrev}><ChevronLeftIcon size={18} /></ToolButton>
          <ToolButton label="Older (j)" onPress={() => onNext?.()} disabled={!onNext}><ChevronRightIcon size={18} /></ToolButton>
        </div>
      </div>

      <div className="flex-1 animate-fade-up">
        <div className="flex items-start gap-3 px-4 pt-5 pb-3 sm:px-6">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl leading-snug font-normal break-words text-text-primary sm:text-[22px]">{data.subject || "(no subject)"}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="inline-flex h-6 items-center gap-1.5 rounded-md px-2 text-xs font-medium" style={{ background: `${data.mailbox.colour}1f`, color: data.mailbox.colour }}>
                <span className="size-1.5 rounded-full" style={{ background: data.mailbox.colour }} />{data.mailbox.name}
              </span>
              {inInbox && <span className="inline-flex h-6 items-center rounded-md bg-background-gray-secondary_alt px-2 text-xs text-text-secondary">Inbox</span>}
              {userLabels.map((chip) => (
                <span key={chip.id} className="inline-flex h-6 items-center gap-1 rounded-md pr-1 pl-2 text-xs font-medium" style={{ background: chip.colour || "#e5e7eb", color: chip.text_colour || "#111827" }}>
                  {chip.name}
                  {perms?.send && <button type="button" aria-label={`Remove label ${chip.name}`} onClick={() => act({ action: "remove_labels", label_ids: [chip.id] })} className="rounded p-0.5 opacity-70 hover:bg-black/10 hover:opacity-100"><CloseIcon size={12} /></button>}
                </span>
              ))}
              {data.snoozed_until && <span className="inline-flex h-6 items-center gap-1 rounded-md bg-warning-500/15 px-2 text-xs text-badge-warning-text"><SnoozeIcon size={12} />Snoozed until {fullDate(data.snoozed_until)}</span>}
            </div>
          </div>
          <button type="button" onClick={() => act({ action: data.is_starred ? "unstar" : "star" })} aria-pressed={!!data.is_starred} aria-label={data.is_starred ? "Unstar (s)" : "Star (s)"}
            className={cn("flex size-10 shrink-0 items-center justify-center rounded-full hover:bg-background-gray-secondary_alt", data.is_starred ? "text-warning-500" : "text-icon-tertiary")}>
            <StarIcon fill={data.is_starred ? "currentColor" : "none"} />
          </button>
        </div>

        <div className="border-b border-card-border">
          {shownMessages.map((message, index) => {
            if (hidden.has(message.id)) {
              if (message.id !== collapsedMiddle[0].id) return null;
              return (
                <div key="older" className="relative flex items-center border-t border-card-border py-1.5">
                  <span aria-hidden="true" className="absolute inset-x-0 top-1/2 border-t border-dashed border-card-border" />
                  <button type="button" onClick={() => setShowAll(true)} className="relative mx-auto flex size-9 items-center justify-center rounded-full border border-card-border bg-card-surface-area text-xs font-semibold text-text-secondary shadow-xs hover:bg-background-gray-secondary_alt" aria-label={`Show ${collapsedMiddle.length} older messages`}>
                    {collapsedMiddle.length}
                  </button>
                </div>
              );
            }
            return (
              <MessageCard key={message.id} message={message} last={index === messages.length - 1} expanded={expanded.has(message.id)} myEmail={data.mailbox.email}
                imagesShown={imagesFor.has(message.id) && !!imageData}
                canSend={!!perms?.send}
                onToggle={() => setExpanded((set) => { const next = new Set(set); if (next.has(message.id)) next.delete(message.id); else next.add(message.id); return next; })}
                actions={messageActions} />
            );
          })}
        </div>

        <div ref={replyRef} className="px-4 py-5 sm:px-6">
          {reply ? (
            <InlineReply init={reply} onClose={() => setReply(null)} onPopOut={(state) => { setReply(null); openCompose(state); }}
              onSent={() => client.invalidateQueries({ queryKey: mailKeys.thread(data.id) })} />
          ) : perms?.send && lastMessage ? (
            <div className="flex flex-wrap gap-2 sm:pl-[52px]">
              {(() => { const mode = defaultReplyMode(lastMessage); return (
                <>
                  <button type="button" onClick={() => startReply(lastMessage, mode)} className="inline-flex h-10 items-center gap-2 rounded-full border border-card-border px-5 text-sm font-medium text-text-primary hover:bg-background-gray-secondary_alt focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
                    {mode === "reply_all" ? <ReplyAllIcon size={18} /> : <ReplyIcon size={18} />}{mode === "reply_all" ? "Reply all" : "Reply"}
                  </button>
                  <button type="button" onClick={() => startReply(lastMessage, mode === "reply_all" ? "reply" : "reply_all")} className="inline-flex h-10 items-center gap-2 rounded-full border border-card-border px-5 text-sm font-medium text-text-primary hover:bg-background-gray-secondary_alt focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
                    {mode === "reply_all" ? <ReplyIcon size={18} /> : <ReplyAllIcon size={18} />}{mode === "reply_all" ? "Reply" : "Reply all"}
                  </button>
                </>
              ); })()}
              <button type="button" onClick={() => startReply(lastMessage, "forward")} className="inline-flex h-10 items-center gap-2 rounded-full border border-card-border px-5 text-sm font-medium text-text-primary hover:bg-background-gray-secondary_alt focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
                <ForwardIcon size={18} />Forward
              </button>
            </div>
          ) : (
            <p className="text-sm text-text-tertiary sm:pl-[52px]">You can read this mailbox but not send from it.</p>
          )}
        </div>

        <InternalPanel thread={data} />
      </div>

      <SnoozePopover anchor={snoozeRef} isOpen={snoozeOpen} onOpenChange={setSnoozeOpen} onPick={(date) => act({ action: "snooze", until: date.toISOString() })} />
      <LabelPopover anchor={labelMode === "move" ? moveRef : labelRef} isOpen={!!labelMode} onOpenChange={(open) => !open && setLabelMode(null)} mode={labelMode ?? "label"}
        labels={labels.data ?? []} threads={[data]}
        onApply={(change) => {
          if ("move" in change) act(change.move === "INBOX" ? { action: "move_to_inbox" } : { action: "move_to_label", label_ids: [change.move] });
          else {
            if (change.add.length) act({ action: "add_labels", label_ids: change.add });
            if (change.remove.length) act({ action: "remove_labels", label_ids: change.remove });
          }
        }} />
      <ConfirmDialog isOpen={confirmDelete} onOpenChange={setConfirmDelete} title="Delete forever?"
        body="This conversation will be permanently deleted from the mailbox. This can't be undone." confirmLabel="Delete forever"
        onConfirm={() => act({ action: "delete_forever" })} />
    </div>
  );
}

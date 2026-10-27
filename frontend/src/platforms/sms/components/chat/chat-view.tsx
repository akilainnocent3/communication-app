"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/tailgrids/core/dropdown";
import { Skeleton } from "@/components/tailgrids/core/skeleton";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import {
  ArchiveIcon, ArrowLeftIcon, BlockIcon, CheckCircleIcon, DotsVerticalIcon, InboxIcon, InfoIcon, MuteIcon, PinIcon, SearchIcon, SpamIcon, StarIcon,
  UnreadIcon, WarningIcon,
} from "@/components/ui/icons";
import { RequestState } from "@/components/ui/request-state";
import { m } from "@/i18n";
import { shortDate } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { SmsActionName, SmsComposeResult, SmsMessage } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { useShortcuts } from "@/platforms/gmail/shortcuts";
import { useConversationActions } from "../../api/actions";
import { smsKeys } from "../../api/keys";
import { useConversation, useDevice, useMessageSearch, useMessages } from "../../api/queries";
import { Composer } from "./composer";
import { MessageBubble } from "./message-bubble";

function dayLabel(iso: string) {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(Date.now() - 86_400_000);
  if (date.toDateString() === today.toDateString()) return m.sms.chat.today;
  if (date.toDateString() === yesterday.toDateString()) return m.sms.chat.yesterday;
  return shortDate(iso);
}

function ToolButton({ label, onPress, children, active }: { label: string; onPress: () => void; children: React.ReactNode; active?: boolean }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onPress} aria-pressed={active}
      className={cn("flex size-9 shrink-0 items-center justify-center rounded-full text-icon-secondary transition-colors hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none [&_svg]:size-[18px]", active && "bg-primary-500/10 text-primary-600 dark:text-primary-300")}>
      {children}
    </button>
  );
}

export function ChatSkeleton() {
  return (
    <div role="status" aria-label="Loading conversation" className="flex flex-col gap-3 px-4 py-5">
      <Skeleton className="h-6 w-48" />
      {[60, 40, 70, 30, 55].map((w, i) => <Skeleton key={i} className={cn("h-10 rounded-2xl", i % 2 ? "self-end" : "")} style={{ width: `${w}%` }} />)}
    </div>
  );
}

export type ChatViewProps = {
  conversationId: number;
  layout: "pane" | "page";
  folder: string;
  onBack: () => void;
  onRemoved: () => void;
  detailsOpen: boolean;
  onToggleDetails: () => void;
};

const REMOVES = new Set<SmsActionName>(["archive", "unarchive", "spam", "not_spam", "block", "unblock"]);

export function ChatView({ conversationId, layout, onBack, onRemoved, detailsOpen, onToggleDetails }: ChatViewProps) {
  const { me } = useSession();
  const client = useQueryClient();
  const conversation = useConversation(conversationId);
  const data = conversation.data;
  const device = useDevice(data?.device.id);
  const messages = useMessages(conversationId);
  const { run } = useConversationActions();
  const [searching, setSearching] = useState(false);
  const [q, setQ] = useState("");
  const search = useMessageSearch(conversationId, q);
  const scroller = useRef<HTMLDivElement>(null);
  usePageTitle(data ? data.title : null);

  const items = useMemo(() => (messages.data?.pages.flatMap((page) => page.results) ?? []).slice().reverse(), [messages.data]);
  const shown = searching && q.trim().length >= 2 ? (search.data?.results ?? []).slice().reverse() : items;
  const lastId = items[items.length - 1]?.id;

  // Stick to the bottom when new messages arrive (unless the user scrolled up to read history).
  const nearBottom = useRef(true);
  useLayoutEffect(() => {
    const box = scroller.current;
    if (box && nearBottom.current) box.scrollTop = box.scrollHeight;
  }, [lastId, shown.length]);

  // "Another admin replied since you opened this": admin messages from someone else queued after this chat opened.
  const [openedAt] = useState(() => Date.now());
  const [dismissed, setDismissed] = useState(false);
  const myId = me?.user.id;
  const later = items.filter((item) => item.origin === "admin" && !item.is_scheduled && item.sent_by && item.sent_by.id !== myId && new Date(item.at).getTime() > openedAt);
  const otherReply = later.length ? later[later.length - 1].sent_by!.display_name : null;

  const act = async (action: SmsActionName) => {
    if (REMOVES.has(action)) onRemoved();
    await run({ action, conversation_ids: [conversationId] });
  };

  useShortcuts({
    u: onBack,
    e: () => data?.permissions.send && act(data.is_archived ? "unarchive" : "archive"),
    "!": () => data?.permissions.send && act("spam"),
    "Shift+U": () => act("unread"),
    s: () => data && act(data.is_starred ? "unstar" : "star"),
  });

  if (conversation.isPending) return <ChatSkeleton />;
  if (conversation.error || !data) return <div className="p-4"><RequestState loading={false} error={errorMessage(conversation.error)} onRetry={() => conversation.refetch()} /></div>;

  const perms = data.permissions;
  const saved = data.participants.some((p) => p.name);
  const subtitle = saved ? data.participants.map((p) => p.display).join(", ") : data.participants.length > 1 ? `${data.participants.length} people` : "";
  const deviceName = data.device.name;
  const showSim = (device.data?.sims.length ?? 0) > 1;

  const retry = async (message: SmsMessage) => {
    try {
      await mutate<SmsComposeResult>(`sms/messages/${message.id}/retry/`, "POST");
      client.invalidateQueries({ queryKey: smsKeys.messages(conversationId) });
      toast.success(m.sms.composer.sent);
    } catch (error) { toast.error(errorMessage(error)); }
  };
  const cancel = async (message: SmsMessage) => {
    try {
      await mutate(`sms/messages/${message.id}/cancel/`, "POST");
      client.invalidateQueries({ queryKey: smsKeys.messages(conversationId) });
      toast(m.sms.composer.undone);
    } catch (error) { toast.error(errorMessage(error)); }
  };

  const withDays = shown.map((message, index) => ({ message, day: dayLabel(message.at), header: index === 0 || dayLabel(shown[index - 1].at) !== dayLabel(message.at) }));
  return (
    <section className="flex h-full min-h-0 flex-col" data-chat-view="" aria-label={data.title}>
      <header className="flex shrink-0 items-center gap-1 border-b border-card-border px-2 py-2 sm:px-3">
        {layout === "page" && <ToolButton label="Back to list (u)" onPress={onBack}><ArrowLeftIcon /></ToolButton>}
        <div className="min-w-0 flex-1 px-1">
          <h2 className="flex items-center gap-2 truncate text-base font-semibold text-text-primary">
            <span className="truncate">{data.title}</span>
            {data.is_pinned && <PinIcon size={14} className="shrink-0 text-icon-tertiary" />}
          </h2>
          <p className="truncate text-xs text-text-tertiary">
            {subtitle && <span>{subtitle} · </span>}
            <span style={{ color: data.device.colour }}>●</span> {deviceName}
            {data.device_status && !(data.device_status as { online?: boolean }).online && <span> · {m.sms.offline}</span>}
          </p>
        </div>
        <ToolButton label={m.sms.searchInChat} onPress={() => { setSearching((v) => !v); setQ(""); }} active={searching}><SearchIcon /></ToolButton>
        {perms.send && <ToolButton label={data.is_archived ? `${m.sms.actions.unarchive} (e)` : `${m.sms.actions.archive} (e)`} onPress={() => act(data.is_archived ? "unarchive" : "archive")}>{data.is_archived ? <InboxIcon /> : <ArchiveIcon />}</ToolButton>}
        <ToolButton label={`${m.sms.actions.unread} (Shift+U)`} onPress={() => { act("unread"); onBack(); }}><UnreadIcon /></ToolButton>
        <ToolButton label="Details" onPress={onToggleDetails} active={detailsOpen}><InfoIcon /></ToolButton>
        <DropdownMenu>
          <DropdownMenuTrigger aria-label="More actions" className="flex size-9 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500"><DotsVerticalIcon /></DropdownMenuTrigger>
          <DropdownMenuContent className="w-56 p-1.5">
            <DropdownMenuItem onAction={() => act(data.is_starred ? "unstar" : "star")} className="px-3 py-2"><StarIcon />{data.is_starred ? m.sms.actions.unstar : m.sms.actions.star}</DropdownMenuItem>
            {perms.send && <DropdownMenuItem onAction={() => act(data.is_pinned ? "unpin" : "pin")} className="px-3 py-2"><PinIcon />{data.is_pinned ? m.sms.actions.unpin : m.sms.actions.pin}</DropdownMenuItem>}
            {perms.send && <DropdownMenuItem onAction={() => act(data.is_muted ? "unmute" : "mute")} className="px-3 py-2"><MuteIcon />{data.is_muted ? m.sms.actions.unmute : m.sms.actions.mute}</DropdownMenuItem>}
            {perms.send && <DropdownMenuItem onAction={() => act(data.state === "done" ? "reopen" : "done")} className="px-3 py-2"><CheckCircleIcon />{data.state === "done" ? m.sms.actions.reopen : m.sms.actions.done}</DropdownMenuItem>}
            {perms.send && <DropdownMenuSeparator />}
            {perms.send && <DropdownMenuItem onAction={() => act(data.is_spam ? "not_spam" : "spam")} className="px-3 py-2"><SpamIcon />{data.is_spam ? m.sms.actions.not_spam : m.sms.actions.spam}</DropdownMenuItem>}
            {perms.manage && <DropdownMenuItem onAction={() => act(data.participants.some((p) => p.is_blocked) ? "unblock" : "block")} className="px-3 py-2 text-error-600 dark:text-error-400"><BlockIcon />{data.participants.some((p) => p.is_blocked) ? m.sms.actions.unblock : m.sms.actions.block}</DropdownMenuItem>}
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      {searching && (
        <div className="shrink-0 border-b border-card-border px-3 py-2">
          <label className="relative block">
            <span className="sr-only">{m.sms.searchInChat}</span>
            <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-icon-tertiary" />
            <input autoFocus value={q} onChange={(event) => setQ(event.target.value)} placeholder={m.sms.searchInChat}
              className="h-9 w-full rounded-full border border-card-border bg-input-background pr-3 pl-9 text-sm text-text-primary outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20" />
          </label>
        </div>
      )}

      {otherReply && !dismissed && (
        <div role="alert" className="flex shrink-0 items-center gap-2 border-b border-warning-500/30 bg-warning-500/10 px-4 py-2 text-xs text-text-primary">
          <WarningIcon size={14} className="shrink-0 text-warning-500" />{m.sms.chat.otherAdminReplied(otherReply)}
          <button type="button" onClick={() => setDismissed(true)} className="ml-auto font-medium text-text-secondary hover:text-text-primary">{m.common.close}</button>
        </div>
      )}

      <div ref={scroller} onScroll={(event) => { const box = event.currentTarget; nearBottom.current = box.scrollHeight - box.scrollTop - box.clientHeight < 120; }}
        className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-4 sm:px-5" role="log" aria-live="polite" aria-label="Messages">
        {!searching && messages.hasNextPage && (
          <div className="mb-4 flex justify-center">
            <button type="button" onClick={() => { nearBottom.current = false; messages.fetchNextPage(); }} disabled={messages.isFetchingNextPage}
              className="rounded-full border border-card-border px-3 py-1 text-xs font-medium text-text-secondary hover:bg-background-gray-secondary_alt">{m.sms.chat.loadOlder}</button>
          </div>
        )}
        {messages.isPending ? <ChatSkeleton /> : (
          <div className="flex flex-col gap-2.5">
            {withDays.map(({ message, day, header }) => {
              return (
                <div key={message.id} className="flex flex-col gap-2.5">
                  {header && <p className="my-1 self-center rounded-full bg-background-gray-secondary_alt px-3 py-0.5 text-[11px] font-medium text-text-tertiary">{day}</p>}
                  <MessageBubble message={message} deviceName={deviceName} canReveal={perms.reveal} canSend={perms.send} showSim={showSim} onRetry={retry} onCancel={cancel} />
                </div>
              );
            })}
            {searching && q.trim().length >= 2 && search.data && !search.data.results.length && <p className="py-6 text-center text-sm text-text-tertiary">{m.sms.empty.search(q)}</p>}
          </div>
        )}
      </div>

      <Composer device={device.data} conversation={conversationId} defaultSim={data.sim?.id ?? null} canSend={perms.send}
        onSent={() => { nearBottom.current = true; client.invalidateQueries({ queryKey: smsKeys.messages(conversationId) }); }} />
    </section>
  );
}

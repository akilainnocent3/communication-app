"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useRef, useState } from "react";
import { useDefaultLayout } from "react-resizable-panels";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/tailgrids/core/resizable";
import { ButtonLink } from "@/components/tailgrids/core/button-link";
import { ArchiveIcon, CheckCircleIcon, MessageIcon, PencilIcon, PinIcon, PlusIcon, ReadIcon, RefreshIcon, SearchIcon, SpamIcon, UnreadIcon } from "@/components/ui/icons";
import { EmptyState } from "@/components/ui/empty-state";
import { RequestState } from "@/components/ui/request-state";
import { useSession } from "@/components/shell/session-provider";
import { useMediaQuery } from "@/hooks/use-media-query";
import { m } from "@/i18n";
import { errorMessage } from "@/services/api/client";
import type { ConversationSummary, SmsActionRequest } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { useShortcuts } from "@/platforms/gmail/shortcuts";
import { useConversationActions } from "../../api/actions";
import { smsKeys, type ConversationListParams, type SmsFolder } from "../../api/keys";
import { useConversationList, useCurrentDevice, useDeviceScope, useDeviceSummaries } from "../../api/queries";
import { openNewMessage } from "../../compose-store";
import { ChatView } from "../chat/chat-view";
import { DetailsPanel } from "../details-panel";
import { ConversationList, ConversationListSkeleton } from "./conversation-list";
import type { RowAction } from "./conversation-row";

const safeStorage = {
  getItem: (key: string) => { try { return window.localStorage.getItem(key); } catch { return null; } },
  setItem: (key: string, value: string) => { try { window.localStorage.setItem(key, value); } catch { /* not remembered */ } },
};

function ToolbarButton({ label, onPress, children, className }: { label: string; onPress: () => void; children: React.ReactNode; className?: string }) {
  return (
    <button type="button" onClick={onPress} aria-label={label} title={label}
      className={cn("flex size-9 shrink-0 items-center justify-center rounded-full text-icon-secondary transition-colors hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none [&_svg]:size-[18px]", className)}>
      {children}
    </button>
  );
}

type Chip = { key: string; label: string; active: boolean; onPress: () => void };

function FilterChips({ chips }: { chips: Chip[] }) {
  return (
    <div role="toolbar" aria-label="Filters" className="flex shrink-0 gap-1.5 overflow-x-auto border-b border-card-border px-3 py-2 [scrollbar-width:none]">
      {chips.map((chip) => (
        <button key={chip.key} type="button" aria-pressed={chip.active} onClick={chip.onPress}
          className={cn("h-7 shrink-0 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none",
            chip.active ? "border-primary-500 bg-primary-500/10 text-primary-700 dark:text-primary-300" : "border-card-border text-text-secondary hover:bg-background-gray-secondary_alt")}>
          {chip.label}
        </button>
      ))}
    </div>
  );
}

export type SmsWorkspaceProps = { folder: SmsFolder; title: string; icon: React.ReactNode; empty: { title: string; body: string } };

/** SMS inbox: conversation list | chat | details. Switching phone remounts everything (keyed by scope). */
export function SmsWorkspace(props: SmsWorkspaceProps) {
  const [scope] = useDeviceScope();
  return <Workspace key={scope} {...props} />;
}

function Workspace({ folder, title, icon, empty }: SmsWorkspaceProps) {
  const pathname = usePathname();
  const params = useSearchParams();
  const client = useQueryClient();
  const { can } = useSession();
  const [scope] = useDeviceScope();
  const devices = useDeviceSummaries();
  const current = useCurrentDevice();
  const { run } = useConversationActions();
  const desktop = useMediaQuery("(min-width: 1280px)");
  const wide = useMediaQuery("(min-width: 1600px)");
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<{ unread?: boolean; direction?: "in" | "out"; has_mms?: boolean; sim?: number }>({});
  const listParams: ConversationListParams = useMemo(() => ({ device: scope, folder, q: q.trim() || undefined, ...filter }), [scope, folder, q, filter]);
  const list = useConversationList(listParams);
  const rows = useMemo(() => list.data?.pages.flatMap((page) => page.results) ?? [], [list.data]);
  const total = list.data?.pages[0]?.total ?? null;

  const openId = Number(params.get("c")) || null;
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [focusedId, setFocusedId] = useState<number | null>(null);
  // Details are open by default only where there is room for a third pane.
  const [detailsPref, setDetailsOpen] = useState<boolean | null>(null);
  const detailsOpen = detailsPref ?? wide;
  const anchor = useRef<number | null>(null);
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({ id: "cm-sms-panes", storage: safeStorage });

  const ids = useMemo(() => new Set(rows.map((row) => row.id)), [rows]);
  const selectedIds = [...selected].filter((id) => ids.has(id));
  const permsFor = useCallback((row: ConversationSummary) => devices.find((device) => device.id === row.device.id)?.permissions, [devices]);
  const canOrganise = useCallback((row: ConversationSummary) => !!permsFor(row)?.send, [permsFor]);
  const selectedRows = rows.filter((row) => selected.has(row.id));
  const canSendAll = selectedRows.length > 0 && selectedRows.every(canOrganise);
  const multiSim = (current?.sims.length ?? 0) > 1;
  const anySendable = current ? current.permissions.send && current.status === "active" : devices.some((device) => device.permissions.send && device.status === "active");

  const setUrl = useCallback((id: number | null, replace = false) => {
    const next = new URLSearchParams(params.toString());
    if (id) next.set("c", String(id)); else next.delete("c");
    const href = `${pathname}${next.toString() ? `?${next}` : ""}`;
    if (replace) window.history.replaceState(null, "", href); else window.history.pushState(null, "", href);
  }, [params, pathname]);

  const open = useCallback((row: ConversationSummary) => { setFocusedId(row.id); setUrl(row.id); }, [setUrl]);
  const close = useCallback(() => setUrl(null), [setUrl]);
  const advanceFrom = useCallback((id: number) => {
    const index = rows.findIndex((row) => row.id === id);
    const next = rows[index + 1] ?? rows[index - 1];
    setFocusedId(next?.id ?? null);
    if (openId === id) setUrl(next && desktop ? next.id : null, true);
  }, [rows, openId, desktop, setUrl]);

  const rowAction = useCallback((row: ConversationSummary, action: RowAction) => {
    if (action === "archive" || action === "unarchive") advanceFrom(row.id);
    run({ action, conversation_ids: [row.id] });
  }, [run, advanceFrom]);

  const bulk = useCallback(async (action: SmsActionRequest["action"]) => {
    if (!selectedIds.length) return;
    if (openId && selectedIds.includes(openId) && ["archive", "unarchive", "spam", "not_spam"].includes(action)) setUrl(null, true);
    const targets = selectedIds;
    setSelected(new Set());
    await run({ action, conversation_ids: targets }, { count: targets.length });
  }, [selectedIds, openId, setUrl, run]);

  const toggleSelect = useCallback((row: ConversationSummary, range: boolean) => {
    setSelected((now) => {
      const next = new Set(now);
      if (range && anchor.current !== null) {
        const a = rows.findIndex((r) => r.id === anchor.current), b = rows.findIndex((r) => r.id === row.id);
        if (a >= 0 && b >= 0) { for (const r of rows.slice(Math.min(a, b), Math.max(a, b) + 1)) next.add(r.id); return next; }
      }
      if (next.has(row.id)) next.delete(row.id); else next.add(row.id);
      anchor.current = row.id;
      return next;
    });
  }, [rows]);

  const focusIndex = focusedId === null ? -1 : rows.findIndex((row) => row.id === focusedId);
  const move = (delta: number) => {
    if (!rows.length) return;
    const base = openId ? rows.findIndex((row) => row.id === openId) : focusIndex;
    const next = rows[Math.max(0, Math.min(rows.length - 1, (base < 0 ? -1 : base) + delta))];
    setFocusedId(next.id);
    if (openId) setUrl(next.id, true);
  };

  useShortcuts({
    j: () => move(1),
    k: () => move(-1),
    o: () => { const row = rows[focusIndex]; if (row) open(row); },
    Enter: () => { const row = rows[focusIndex]; if (row && !openId) open(row); },
    x: () => { const row = rows[focusIndex]; if (row) toggleSelect(row, false); },
    "/": () => document.getElementById("sms-search")?.focus(),
    ...(selectedIds.length ? {
      e: () => canSendAll && bulk(folder === "archived" ? "unarchive" : "archive"),
      "!": () => canSendAll && bulk("spam"),
      "Shift+I": () => bulk("read"),
      "Shift+U": () => bulk("unread"),
    } : !openId && focusIndex >= 0 ? {
      e: () => canOrganise(rows[focusIndex]) && rowAction(rows[focusIndex], rows[focusIndex].is_archived ? "unarchive" : "archive"),
    } : {}),
  });

  const allSelected = rows.length > 0 && selectedIds.length === rows.length;
  const chips: Chip[] = [
    { key: "all", label: m.sms.filters.all, active: !filter.unread && !filter.direction && !filter.has_mms, onPress: () => setFilter((f) => ({ sim: f.sim })) },
    { key: "unread", label: m.sms.filters.unread, active: !!filter.unread, onPress: () => setFilter((f) => ({ ...f, unread: f.unread ? undefined : true })) },
    { key: "in", label: m.sms.filters.inbound, active: filter.direction === "in", onPress: () => setFilter((f) => ({ ...f, direction: f.direction === "in" ? undefined : "in" })) },
    { key: "out", label: m.sms.filters.outbound, active: filter.direction === "out", onPress: () => setFilter((f) => ({ ...f, direction: f.direction === "out" ? undefined : "out" })) },
    { key: "mms", label: m.sms.filters.mms, active: !!filter.has_mms, onPress: () => setFilter((f) => ({ ...f, has_mms: f.has_mms ? undefined : true })) },
    ...(multiSim ? current!.sims.map((sim) => ({ key: `sim-${sim.id}`, label: sim.label, active: filter.sim === sim.id, onPress: () => setFilter((f) => ({ ...f, sim: f.sim === sim.id ? undefined : sim.id })) })) : []),
  ];

  const toolbar = (
    <div className="flex h-12 shrink-0 items-center gap-0.5 border-b border-card-border px-2 sm:px-3">
      <label className="flex size-9 items-center justify-center rounded-lg hover:bg-background-gray-secondary_alt">
        <input type="checkbox" aria-label={allSelected ? "Deselect all" : "Select all on this page"} checked={allSelected}
          ref={(element) => { if (element) element.indeterminate = selectedIds.length > 0 && !allSelected; }}
          onChange={() => setSelected(allSelected || selectedIds.length ? new Set() : new Set(rows.map((row) => row.id)))}
          className="size-4 rounded border-border-primary text-primary-500 focus:ring-primary-500" />
      </label>
      {selectedIds.length === 0 ? (
        <ToolbarButton label="Refresh" onPress={() => client.invalidateQueries({ queryKey: smsKeys.conversationLists() })}><RefreshIcon className={cn(list.isFetching && !list.isFetchingNextPage && "animate-spin")} /></ToolbarButton>
      ) : (
        <div className="flex min-w-0 items-center gap-0.5 overflow-x-auto [scrollbar-width:none]" role="toolbar" aria-label="Bulk actions">
          {canSendAll && <ToolbarButton label={folder === "archived" ? m.sms.actions.unarchive : `${m.sms.actions.archive} (e)`} onPress={() => bulk(folder === "archived" ? "unarchive" : "archive")}><ArchiveIcon /></ToolbarButton>}
          {canSendAll && <ToolbarButton label={folder === "spam" ? m.sms.actions.not_spam : `${m.sms.actions.spam} (!)`} onPress={() => bulk(folder === "spam" ? "not_spam" : "spam")}><SpamIcon /></ToolbarButton>}
          {selectedRows.some((row) => row.unread_count > 0)
            ? <ToolbarButton label={`${m.sms.actions.read} (Shift+I)`} onPress={() => bulk("read")}><ReadIcon /></ToolbarButton>
            : <ToolbarButton label={`${m.sms.actions.unread} (Shift+U)`} onPress={() => bulk("unread")}><UnreadIcon /></ToolbarButton>}
          {canSendAll && <ToolbarButton label={m.sms.actions.pin} onPress={() => bulk("pin")}><PinIcon /></ToolbarButton>}
          {canSendAll && <ToolbarButton label={m.sms.actions.done} onPress={() => bulk("done")}><CheckCircleIcon /></ToolbarButton>}
          <span className="ml-1 shrink-0 text-xs font-medium whitespace-nowrap text-text-secondary">{selectedIds.length} selected</span>
        </div>
      )}
      <span className="ml-auto mr-1 hidden text-xs text-text-tertiary tabular-nums md:inline">{rows.length ? `1–${rows.length}` : "0"}{total !== null ? ` of ${total.toLocaleString()}` : ""}</span>
    </div>
  );

  const noDevices = devices.length === 0;
  const listBody = list.isPending ? <ConversationListSkeleton /> : list.error && !rows.length ? (
    <div className="p-4"><RequestState loading={false} error={errorMessage(list.error)} onRetry={() => list.refetch()} /></div>
  ) : rows.length === 0 ? (
    <div className="flex-1 overflow-y-auto">
      {noDevices ? (
        <EmptyState icon={<MessageIcon />} title={m.sms.empty.noDevices.title} body={m.sms.empty.noDevices.body}
          action={can("sms.manage_devices") ? <ButtonLink href="/sms/devices?enroll=1"><PlusIcon size={16} />{m.sms.devices.enroll}</ButtonLink> : undefined} />
      ) : <EmptyState icon={q ? <SearchIcon /> : icon} title={q ? m.sms.empty.search(q) : empty.title} body={q ? undefined : empty.body} />}
    </div>
  ) : (
    <ConversationList rows={rows} hasMore={!!list.hasNextPage} loadingMore={list.isFetchingNextPage} onLoadMore={() => { if (!list.isFetchingNextPage) list.fetchNextPage(); }}
      selected={selected} focusedId={focusedId} activeId={desktop ? openId : null} showDevice={scope === "all"} showSim={multiSim || scope === "all"}
      canOrganise={canOrganise} onOpen={open} onToggleSelect={toggleSelect} onAction={rowAction} />
  );

  const listPane = (
    <div className="flex h-full min-h-0 flex-col" data-sms-list="">
      <div className="shrink-0 border-b border-card-border px-3 py-2">
        <label className="relative block">
          <span className="sr-only">{m.sms.search}</span>
          <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-icon-tertiary" />
          <input id="sms-search" type="search" value={q} onChange={(event) => setQ(event.target.value)} placeholder={m.sms.search}
            className="h-10 w-full rounded-full border border-card-border bg-input-background pr-3 pl-9 text-sm text-text-primary outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20" />
        </label>
      </div>
      {toolbar}
      <FilterChips chips={chips} />
      {listBody}
    </div>
  );

  const chat = openId ? (
    <ChatView key={openId} conversationId={openId} layout={desktop ? "pane" : "page"} folder={folder} onBack={close} onRemoved={() => advanceFrom(openId)}
      detailsOpen={detailsOpen} onToggleDetails={() => setDetailsOpen(!detailsOpen)} />
  ) : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-sms-workspace="" aria-label={title}>
      {desktop ? (
        <ResizablePanelGroup orientation="horizontal" defaultLayout={defaultLayout} onLayoutChanged={onLayoutChanged} className="min-h-0 flex-1">
          <ResizablePanel id="list" defaultSize="34%" minSize="320px" className="min-w-0">{listPane}</ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel id="chat" defaultSize={wide ? "44%" : "66%"} minSize="380px" className="min-w-0">
            {chat ?? <EmptyState icon={<MessageIcon />} title={m.sms.empty.noSelection.title} body={m.sms.empty.noSelection.body} />}
          </ResizablePanel>
          {openId && detailsOpen && wide && (
            <>
              <ResizableHandle withHandle />
              <ResizablePanel id="details" defaultSize="22%" minSize="260px" className="min-w-0"><DetailsPanel conversationId={openId} onClose={() => setDetailsOpen(false)} /></ResizablePanel>
            </>
          )}
        </ResizablePanelGroup>
      ) : openId ? (
        <div className="flex min-h-0 flex-1 flex-col">{chat}</div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">{listPane}</div>
      )}
      {openId && detailsOpen && !wide && (
        <div className="fixed inset-y-0 right-0 z-40 w-[min(22rem,100vw)] border-l border-card-border bg-card-surface-area shadow-xl" role="dialog" aria-label="Conversation details">
          <DetailsPanel conversationId={openId} onClose={() => setDetailsOpen(false)} />
        </div>
      )}
      {!desktop && !openId && anySendable && (
        <button type="button" onClick={() => openNewMessage({ device: current?.id })} aria-label={m.sms.newMessage}
          className="fixed right-4 bottom-[max(1rem,env(safe-area-inset-bottom))] z-30 flex h-14 items-center gap-2 rounded-2xl bg-primary-500 px-5 text-sm font-semibold text-white shadow-[0_10px_24px_-8px_rgba(55,88,249,0.7)] transition active:scale-95">
          <PencilIcon /> {m.sms.newMessage}
        </button>
      )}
    </div>
  );
}

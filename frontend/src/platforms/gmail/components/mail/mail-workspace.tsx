"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useCallback, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/tailgrids/core/resizable";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/tailgrids/core/dropdown";
import { useDefaultLayout } from "react-resizable-panels";
import {
  ArchiveIcon, ChevronDownIcon, DoubleCheckIcon, ExpandIcon, InboxIcon, NoSplitIcon, PencilIcon, ReadIcon, RefreshIcon, SearchIcon, SnoozeIcon,
  SpamIcon, SplitIcon, TagIcon, TrashIcon, UnreadIcon,
} from "@/components/ui/icons";
import { EmptyState } from "@/components/ui/empty-state";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RequestState } from "@/components/ui/request-state";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { useMediaQuery } from "@/hooks/use-media-query";
import { errorMessage, mutate, query as qs, request } from "@/services/api/client";
import type { ActionRequest, ThreadPage, ThreadSummary } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { useThreadActions } from "../../api/actions";
import { mailKeys, type ThreadListParams } from "../../api/keys";
import { useLabels, useMailboxScope, useMailboxSummaries, useMailboxes, usePrefetchThread, useThreadList } from "../../api/queries";
import { openCompose } from "../../compose/store";
import { CATEGORY_TABS } from "../../folders";
import { useShortcuts } from "../../shortcuts";
import { ReconnectBanner } from "../mailboxes/reconnect-banner";
import { LabelPopover } from "./label-picker";
import { SearchBar } from "./search-bar";
import { SnoozePopover } from "./snooze-picker";
import { ListSkeleton, ThreadList } from "./thread-list";
import type { RowAction } from "./thread-row";
import { ThreadView } from "./thread-view";

export type WorkspaceProps = {
  title: string;
  label?: string;
  icon: React.ReactNode;
  empty: { title: string; body: string };
  /** Search results page (q comes from the URL). */
  search?: boolean;
};

const safeStorage = {
  getItem: (key: string) => { try { return window.localStorage.getItem(key); } catch { return null; } },
  setItem: (key: string, value: string) => { try { window.localStorage.setItem(key, value); } catch { /* not remembered */ } },
};

function ToolbarButton({ label, onPress, children, buttonRef, className }: { label: string; onPress: () => void; children: React.ReactNode; buttonRef?: React.Ref<HTMLButtonElement>; className?: string }) {
  return (
    <button ref={buttonRef} type="button" onClick={onPress} aria-label={label} title={label}
      className={cn("flex size-9 shrink-0 items-center justify-center rounded-full text-icon-secondary transition-colors hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none [&_svg]:size-[18px]", className)}>
      {children}
    </button>
  );
}

/** Gmail's mail view: search, toolbar, virtualised list and (≥ xl, split mode) a resizable reading pane. */
export function MailWorkspace(props: WorkspaceProps) {
  const [scope] = useMailboxScope();
  // Switching mailbox remounts the whole workspace: selection, focus and queries start fresh.
  return <Workspace key={String(scope)} {...props} />;
}

function Workspace({ title, label, icon, empty, search }: WorkspaceProps) {
  const pathname = usePathname();
  const params = useSearchParams();
  const client = useQueryClient();
  const { preferences, updatePreferences } = useSession();
  const [scope] = useMailboxScope();
  const summaries = useMailboxSummaries();
  const mailboxes = useMailboxes();
  const labels = useLabels(scope === "all" ? undefined : scope);
  const { run } = useThreadActions();
  const prefetch = usePrefetchThread();
  const desktop = useMediaQuery("(min-width: 1280px)");
  const split = desktop && preferences.reading_pane === "right";
  const compact = preferences.density === "compact";

  const q = search ? params.get("q") ?? "" : "";
  const tab = label === "INBOX" ? params.get("tab") ?? "primary" : undefined;
  const capsOf = useCallback((id: number) => mailboxes.data?.find((box) => box.id === id)?.capabilities, [mailboxes.data]);
  const currentCaps = scope === "all" ? undefined : capsOf(scope);
  const showTabs = label === "INBOX" && (scope === "all" ? summaries.some((box) => box.provider !== "imap_smtp") : !!currentCaps?.categories);
  const listParams: ThreadListParams = useMemo(() => ({ mailbox: scope, label: search ? undefined : label, q: q || undefined, category: showTabs ? tab : undefined }), [scope, label, q, search, showTabs, tab]);
  const list = useThreadList(listParams);
  const threads = useMemo(() => list.data?.pages.flatMap((page) => page.results) ?? [], [list.data]);
  const total = list.data?.pages[0]?.total ?? null;

  usePageTitle(search ? { page: "Search", section: "Mail", detail: q || undefined } : null);

  const openId = Number(params.get("thread")) || null;
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [allMatching, setAllMatching] = useState(false);
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const anchorRef = useRef<number | null>(null);
  const [snooze, setSnooze] = useState<{ ids: number[] } | null>(null);
  const snoozeAnchor = useRef<Element | null>(null);
  const [labelMode, setLabelMode] = useState<"label" | "move" | null>(null);
  const labelAnchor = useRef<HTMLButtonElement>(null);
  const moveAnchor = useRef<HTMLButtonElement>(null);
  const toolbarSnooze = useRef<HTMLButtonElement>(null);
  const [confirm, setConfirm] = useState<null | "delete_forever" | "read_all">(null);
  const [serverResults, setServerResults] = useState<ThreadSummary[] | null>(null);
  const [serverBusy, setServerBusy] = useState(false);
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({ id: "cm-mail-panes", storage: safeStorage });

  // Prune selection when threads leave the list (archive, delete…).
  const visibleThreads = serverResults ?? threads;
  const ids = useMemo(() => new Set(visibleThreads.map((thread) => thread.id)), [visibleThreads]);
  const selectedIds = [...selected].filter((id) => ids.has(id));
  const selectedThreads = visibleThreads.filter((thread) => selected.has(thread.id));
  const focusIndex = focusedId === null ? -1 : visibleThreads.findIndex((thread) => thread.id === focusedId);

  const permsFor = useCallback((thread: ThreadSummary) => {
    const box = summaries.find((item) => item.id === thread.mailbox.id);
    return { send: !!box?.permissions.send, delete: !!box?.permissions.delete };
  }, [summaries]);
  const canSendAny = selectedThreads.length > 0 ? selectedThreads.every((thread) => permsFor(thread).send) : false;
  const canDeleteAny = selectedThreads.length > 0 ? selectedThreads.every((thread) => permsFor(thread).delete) : false;
  const singleMailbox = new Set(selectedThreads.map((thread) => thread.mailbox.id)).size === 1;

  const setUrl = useCallback((thread: number | null, replace = false) => {
    const next = new URLSearchParams(params.toString());
    if (thread) next.set("thread", String(thread)); else next.delete("thread");
    const href = `${pathname}${next.toString() ? `?${next}` : ""}`;
    // Shallow update: Next syncs useSearchParams with the native history API and skips the server round trip
    // (router.push is also dropped by the production router on statically prerendered routes like /gmail/search).
    if (replace) window.history.replaceState(null, "", href); else window.history.pushState(null, "", href);
  }, [params, pathname]);

  const open = useCallback((thread: ThreadSummary) => {
    setFocusedId(thread.id);
    // Drafts open in the compose window, like Gmail.
    if (label === "DRAFT") { openCompose({ mailbox: thread.mailbox.id, threadId: thread.id }); return; }
    setUrl(thread.id);
  }, [label, setUrl]);
  const close = useCallback(() => setUrl(null), [setUrl]);

  /** After a removing action, open the next conversation (Gmail's "newer/older" setting: older). */
  const advanceFrom = useCallback((id: number) => {
    const index = visibleThreads.findIndex((thread) => thread.id === id);
    const next = visibleThreads[index + 1] ?? visibleThreads[index - 1];
    setFocusedId(next?.id ?? null);
    if (openId === id) {
      if (next && split) setUrl(next.id, true);
      else setUrl(null, true);
    }
  }, [visibleThreads, openId, split, setUrl]);

  const bulk = useCallback(async (req: Omit<ActionRequest, "thread_ids" | "select_all">) => {
    const targetIds = selectedIds;
    if (!targetIds.length) return;
    const body: ActionRequest = allMatching
      ? { ...req, select_all: { mailbox: String(scope), label: search ? undefined : label, category: listParams.category, q: q || undefined } }
      : { ...req, thread_ids: targetIds };
    if (openId && targetIds.includes(openId) && ["archive", "trash", "spam", "delete_forever", "move_to_label", "snooze"].includes(req.action)) setUrl(null, true);
    setSelected(new Set());
    setAllMatching(false);
    await run(body, { count: allMatching && total ? total : targetIds.length });
  }, [selectedIds, allMatching, scope, label, search, listParams.category, q, openId, setUrl, run, total]);

  const rowAction = useCallback((thread: ThreadSummary, action: RowAction) => {
    if (["archive", "trash"].includes(action)) advanceFrom(thread.id);
    run({ action, thread_ids: [thread.id] });
  }, [run, advanceFrom]);

  const toggleSelect = useCallback((thread: ThreadSummary, range: boolean) => {
    setAllMatching(false);
    setSelected((current) => {
      const next = new Set(current);
      if (range && anchorRef.current !== null) {
        const a = visibleThreads.findIndex((t) => t.id === anchorRef.current);
        const b = visibleThreads.findIndex((t) => t.id === thread.id);
        if (a >= 0 && b >= 0) { for (const t of visibleThreads.slice(Math.min(a, b), Math.max(a, b) + 1)) next.add(t.id); return next; }
      }
      if (next.has(thread.id)) next.delete(thread.id); else next.add(thread.id);
      anchorRef.current = thread.id;
      return next;
    });
  }, [visibleThreads]);

  const selectBy = (kind: "all" | "none" | "read" | "unread" | "starred" | "unstarred") => {
    setAllMatching(false);
    const pick = { all: () => true, none: () => false, read: (t: ThreadSummary) => !t.is_unread, unread: (t: ThreadSummary) => !!t.is_unread, starred: (t: ThreadSummary) => !!t.is_starred, unstarred: (t: ThreadSummary) => !t.is_starred }[kind];
    setSelected(new Set(visibleThreads.filter(pick).map((t) => t.id)));
  };

  const move = (delta: number) => {
    if (!visibleThreads.length) return;
    const base = openId ? visibleThreads.findIndex((t) => t.id === openId) : focusIndex;
    const nextIndex = Math.max(0, Math.min(visibleThreads.length - 1, (base < 0 ? -1 : base) + delta));
    const next = visibleThreads[nextIndex];
    setFocusedId(next.id);
    if (openId) setUrl(next.id, true);
  };

  useShortcuts({
    j: () => move(1),
    k: () => move(-1),
    o: () => { const t = visibleThreads[focusIndex]; if (t) open(t); },
    Enter: () => { const t = visibleThreads[focusIndex]; if (t && !openId) open(t); },
    x: () => { const t = visibleThreads[focusIndex]; if (t) toggleSelect(t, false); },
    ...(selectedIds.length ? {
      e: () => canSendAny && bulk({ action: "archive" }),
      "#": () => canDeleteAny && bulk({ action: "trash" }),
      "!": () => canSendAny && bulk({ action: "spam" }),
      "Shift+I": () => bulk({ action: "read" }),
      "Shift+U": () => bulk({ action: "unread" }),
      s: () => bulk({ action: "star" }),
      l: () => canSendAny && singleMailbox && setLabelMode("label"),
      b: () => { if (canSendAny) { snoozeAnchor.current = toolbarSnooze.current; setSnooze({ ids: selectedIds }); } },
    } : !openId && focusIndex >= 0 ? {
      e: () => rowAction(visibleThreads[focusIndex], "archive"),
      "#": () => rowAction(visibleThreads[focusIndex], "trash"),
      s: () => rowAction(visibleThreads[focusIndex], visibleThreads[focusIndex].is_starred ? "unstar" : "star"),
    } : {}),
  });

  // Keep focus on the open conversation so j/k continue from it.
  const [seenOpen, setSeenOpen] = useState(openId);
  if (seenOpen !== openId) { setSeenOpen(openId); if (openId) setFocusedId(openId); }
  const [seenQuery, setSeenQuery] = useState(q);
  if (seenQuery !== q) { setSeenQuery(q); setServerResults(null); }

  const refresh = async () => {
    if (scope !== "all") mutate(`mail/mailboxes/${scope}/sync/`, "POST").catch(() => undefined);
    await client.invalidateQueries({ queryKey: mailKeys.threadLists() });
    client.invalidateQueries({ queryKey: ["mail", "labels"] });
  };

  const markAllRead = async () => {
    await run({ action: "read", select_all: { mailbox: String(scope), label: search ? undefined : label, category: listParams.category, q: q || undefined } }, { count: total ?? threads.length });
  };

  const serverSearch = async () => {
    if (scope === "all") return;
    setServerBusy(true);
    try {
      const page = await request<ThreadPage>(`mail/threads/server-search/${qs({ mailbox: scope, q })}`);
      setServerResults(page.results);
      if (!page.results.length) toast("No more results in the full mailbox.");
    } catch (error) { toast.error(errorMessage(error)); } finally { setServerBusy(false); }
  };

  const allSelected = visibleThreads.length > 0 && selectedIds.length === visibleThreads.length;
  const someSelected = selectedIds.length > 0 && !allSelected;
  const loadedCount = visibleThreads.length;

  const toolbar = (
    <div className="flex h-12 shrink-0 items-center gap-0.5 border-b border-card-border px-2 sm:px-3">
      <div className="flex items-center rounded-lg hover:bg-background-gray-secondary_alt">
        <label className="flex size-9 items-center justify-center">
          <input type="checkbox" aria-label={allSelected ? "Deselect all" : "Select all on this page"} checked={allSelected}
            ref={(element) => { if (element) element.indeterminate = someSelected; }}
            onChange={() => selectBy(allSelected || someSelected ? "none" : "all")}
            className="size-4 rounded border-border-primary text-primary-500 focus:ring-primary-500" />
        </label>
        <DropdownMenu>
          <DropdownMenuTrigger aria-label="Select conversations" className="-ml-2 flex h-9 w-5 items-center justify-center text-icon-tertiary hover:text-text-primary"><ChevronDownIcon size={14} /></DropdownMenuTrigger>
          <DropdownMenuContent className="w-44 p-1.5">
            {(["all", "none", "read", "unread", "starred", "unstarred"] as const).map((kind) => (
              <DropdownMenuItem key={kind} onAction={() => selectBy(kind)} className="px-3 py-2 capitalize">{kind}</DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {selectedIds.length === 0 ? (
        <>
          <ToolbarButton label="Refresh" onPress={refresh}><RefreshIcon className={cn(list.isFetching && !list.isFetchingNextPage && "animate-spin")} /></ToolbarButton>
          <DropdownMenu>
            <DropdownMenuTrigger aria-label="More" className="flex size-9 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500"><ChevronDownIcon /></DropdownMenuTrigger>
            <DropdownMenuContent className="w-52 p-1.5">
              <DropdownMenuItem onAction={() => setConfirm("read_all")} className="px-3 py-2"><DoubleCheckIcon />Mark all as read</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </>
      ) : (
        <div className="flex min-w-0 items-center gap-0.5 overflow-x-auto [scrollbar-width:none]" role="toolbar" aria-label="Bulk actions">
          {canSendAny && label !== "SPAM" && label !== "TRASH" && <ToolbarButton label="Archive (e)" onPress={() => bulk({ action: "archive" })}><ArchiveIcon /></ToolbarButton>}
          {canSendAny && (label === "SPAM" || label === "TRASH") && <ToolbarButton label="Move to Inbox" onPress={() => bulk({ action: label === "SPAM" ? "not_spam" : "untrash" })}><InboxIcon /></ToolbarButton>}
          {canSendAny && label !== "SPAM" && <ToolbarButton label="Report spam (!)" onPress={() => bulk({ action: "spam" })}><SpamIcon /></ToolbarButton>}
          {canDeleteAny && (label === "TRASH" || label === "SPAM"
            ? <ToolbarButton label="Delete forever" className="text-error-500" onPress={() => setConfirm("delete_forever")}><TrashIcon /></ToolbarButton>
            : <ToolbarButton label="Delete (#)" onPress={() => bulk({ action: "trash" })}><TrashIcon /></ToolbarButton>)}
          <span aria-hidden="true" className="mx-1 h-5 w-px shrink-0 bg-card-border" />
          {selectedThreads.some((t) => t.is_unread)
            ? <ToolbarButton label="Mark as read (Shift+I)" onPress={() => bulk({ action: "read" })}><ReadIcon /></ToolbarButton>
            : <ToolbarButton label="Mark as unread (Shift+U)" onPress={() => bulk({ action: "unread" })}><UnreadIcon /></ToolbarButton>}
          {canSendAny && <ToolbarButton label="Snooze (b)" buttonRef={toolbarSnooze} onPress={() => { snoozeAnchor.current = toolbarSnooze.current; setSnooze({ ids: selectedIds }); }}><SnoozeIcon /></ToolbarButton>}
          {canSendAny && singleMailbox && <ToolbarButton label="Move to" buttonRef={moveAnchor} onPress={() => setLabelMode("move")}><ExpandIcon /></ToolbarButton>}
          {canSendAny && singleMailbox && <ToolbarButton label="Labels (l)" buttonRef={labelAnchor} onPress={() => setLabelMode("label")}><TagIcon /></ToolbarButton>}
          <span className="ml-1 shrink-0 text-xs font-medium whitespace-nowrap text-text-secondary">{allMatching ? `All ${total ?? ""}` : selectedIds.length} selected</span>
        </div>
      )}
      <div className="ml-auto flex shrink-0 items-center gap-0.5">
        <span className="mr-1 hidden text-xs text-text-tertiary tabular-nums md:inline">
          {loadedCount ? `1–${loadedCount}` : "0"}{total !== null ? ` of ${total.toLocaleString()}` : ""}
        </span>
        {desktop && (
          <ToolbarButton label={split ? "No split" : "Vertical split"} onPress={() => updatePreferences({ reading_pane: split ? "none" : "right" }).catch((error) => toast.error(errorMessage(error)))}>
            {split ? <NoSplitIcon /> : <SplitIcon />}
          </ToolbarButton>
        )}
      </div>
    </div>
  );

  const selectAllBanner = allSelected && total !== null && total > loadedCount && (
    <div role="status" className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-b border-card-border bg-primary-500/5 px-4 py-2 text-xs text-text-secondary">
      {allMatching ? (
        <>All {total.toLocaleString()} conversations in {title} are selected. <button type="button" className="font-semibold text-primary-600 hover:underline dark:text-primary-300" onClick={() => { setAllMatching(false); setSelected(new Set()); }}>Clear selection</button></>
      ) : (
        <>All {loadedCount} conversations on this page are selected. <button type="button" className="font-semibold text-primary-600 hover:underline dark:text-primary-300" onClick={() => setAllMatching(true)}>Select all {total.toLocaleString()} conversations in {title}</button></>
      )}
    </div>
  );

  const tabs = showTabs && (
    <div role="tablist" aria-label="Inbox categories" className="flex shrink-0 overflow-x-auto border-b border-card-border [scrollbar-width:none]">
      {CATEGORY_TABS.map((item) => {
        const active = tab === item.key;
        return (
          <button key={item.key} role="tab" type="button" aria-selected={active} onClick={() => {
            const next = new URLSearchParams(params.toString());
            if (item.key === "primary") next.delete("tab"); else next.set("tab", item.key);
            next.delete("thread");
            window.history.replaceState(null, "", `${pathname}${next.toString() ? `?${next}` : ""}`);
          }}
            className={cn("relative flex h-12 min-w-28 shrink-0 items-center gap-2 px-4 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none focus-visible:ring-inset",
              active ? "text-primary-600 after:absolute after:inset-x-3 after:bottom-0 after:h-[3px] after:rounded-t-full after:bg-primary-500 dark:text-primary-300" : "text-text-secondary hover:bg-background-gray-secondary_alt/60")}>
            {item.title}
          </button>
        );
      })}
    </div>
  );

  const searchFooter = search && q && (
    <div className="flex flex-col items-center gap-2 px-4 py-6 text-center text-sm text-text-tertiary">
      {serverResults ? <p>Showing results from the full mailbox.</p> : scope === "all" ? (
        <p>Choose one mailbox to search full message bodies in Gmail.</p>
      ) : currentCaps?.server_search ? (
        <button type="button" disabled={serverBusy} onClick={serverSearch} className="inline-flex items-center gap-2 rounded-full border border-card-border px-4 py-2 font-medium text-text-primary hover:bg-background-gray-secondary_alt disabled:opacity-60">
          <SearchIcon size={16} />{serverBusy ? "Searching the mailbox…" : "Search full message bodies in Gmail"}
        </button>
      ) : null}
    </div>
  );

  const listBody = list.isPending ? (
    <ListSkeleton compact={compact} />
  ) : list.error && !threads.length ? (
    <div className="p-4"><RequestState loading={false} error={errorMessage(list.error)} onRetry={() => list.refetch()} /></div>
  ) : visibleThreads.length === 0 ? (
    <div className="flex-1 overflow-y-auto">
      <EmptyState icon={search ? <SearchIcon /> : icon} title={search ? (q ? `No results for “${q}”` : "Search your mail") : empty.title}
        body={search ? "Try different words, check the spelling, or use the advanced search options." : empty.body}
        action={!search && label === "INBOX" && summaries.length === 0 ? <Link href="/gmail/mailboxes/new" className="inline-flex h-10 items-center rounded-lg bg-primary-500 px-4 text-sm font-medium text-white hover:bg-primary-600">Add your first mailbox</Link> : undefined} />
      {searchFooter}
    </div>
  ) : (
    <ThreadList
      threads={visibleThreads}
      hasMore={!serverResults && !!list.hasNextPage}
      loadingMore={list.isFetchingNextPage}
      onLoadMore={() => { if (!list.isFetchingNextPage) list.fetchNextPage(); }}
      selected={selected}
      focusedId={focusedId}
      activeId={split ? openId : null}
      showMailbox={scope === "all"}
      compact={compact}
      swipeLeft={preferences.swipe_left}
      swipeRight={preferences.swipe_right}
      permissionsFor={permsFor}
      onOpen={open}
      onToggleSelect={toggleSelect}
      onAction={rowAction}
      onSnooze={(thread, anchor) => { snoozeAnchor.current = anchor; setSnooze({ ids: [thread.id] }); }}
      onHover={(thread) => prefetch(thread.id)}
      footer={searchFooter}
    />
  );

  const listPane = (
    <div className="flex h-full min-h-0 flex-col">
      {toolbar}
      {tabs}
      {selectAllBanner}
      {listBody}
    </div>
  );

  const position = openId ? { index: Math.max(0, visibleThreads.findIndex((t) => t.id === openId)), total } : undefined;
  const openIndex = openId ? visibleThreads.findIndex((t) => t.id === openId) : -1;
  const threadView = openId ? (
    <ThreadView
      key={openId}
      threadId={openId}
      layout={split ? "pane" : "page"}
      label={label}
      position={position}
      onBack={close}
      onPrev={openIndex > 0 ? () => move(-1) : undefined}
      onNext={openIndex >= 0 && openIndex < visibleThreads.length - 1 ? () => move(1) : undefined}
      onRemoved={() => advanceFrom(openId)}
    />
  ) : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-mail-workspace="">
      <div className="flex shrink-0 items-center gap-3 border-b border-card-border px-3 py-2 sm:px-4">
        <SearchBar className="min-w-0 flex-1 xl:max-w-2xl" />
      </div>
      {scope !== "all" && <ReconnectBanner mailboxId={scope} />}
      {split ? (
        <ResizablePanelGroup orientation="horizontal" defaultLayout={defaultLayout} onLayoutChanged={onLayoutChanged} className="min-h-0 flex-1">
          <ResizablePanel id="list" defaultSize="44%" minSize="360px" className="min-w-0">{listPane}</ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel id="reader" defaultSize="56%" minSize="420px" className="min-w-0">
            <div className="scrollbar-thin h-full overflow-y-auto">
              {threadView ?? <EmptyState icon={<InboxIcon />} title={selectedIds.length ? `${selectedIds.length} conversation${selectedIds.length > 1 ? "s" : ""} selected` : "No conversation selected"} body="Pick a conversation from the list, or use j and k to move through it." />}
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      ) : openId ? (
        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">{threadView}</div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">{listPane}</div>
      )}

      {!desktop && !openId && (
        <button type="button" onClick={() => openCompose({ mailbox: scope === "all" ? undefined : scope })} aria-label="Compose"
          className="fixed right-4 bottom-[max(1rem,env(safe-area-inset-bottom))] z-30 flex h-14 items-center gap-2 rounded-2xl bg-primary-500 px-5 text-sm font-semibold text-white shadow-[0_10px_24px_-8px_rgba(55,88,249,0.7)] transition active:scale-95">
          <PencilIcon /> Compose
        </button>
      )}

      <SnoozePopover anchor={snoozeAnchor} isOpen={!!snooze} onOpenChange={(value) => !value && setSnooze(null)}
        onPick={(date) => {
          const targets = snooze?.ids ?? [];
          if (targets.length === 1 && !selectedIds.length) { advanceFrom(targets[0]); run({ action: "snooze", thread_ids: targets, until: date.toISOString() }); }
          else bulk({ action: "snooze", until: date.toISOString() });
        }} />
      <LabelPopover anchor={labelMode === "move" ? moveAnchor : labelAnchor} isOpen={!!labelMode} onOpenChange={(value) => !value && setLabelMode(null)} mode={labelMode ?? "label"}
        labels={labels.data ?? []} threads={selectedThreads}
        onApply={(change) => {
          if ("move" in change) bulk(change.move === "INBOX" ? { action: "move_to_inbox" } : { action: "move_to_label", label_ids: [change.move] });
          else {
            if (change.add.length) bulk({ action: "add_labels", label_ids: change.add });
            if (change.remove.length) run({ action: "remove_labels", thread_ids: selectedIds, label_ids: change.remove });
          }
        }} />
      <ConfirmDialog isOpen={confirm === "delete_forever"} onOpenChange={(value) => !value && setConfirm(null)} title="Delete forever?"
        body={`${allMatching ? `All ${total} conversations` : selectedIds.length === 1 ? "This conversation" : `${selectedIds.length} conversations`} will be permanently deleted. This can't be undone.`}
        confirmLabel="Delete forever" onConfirm={() => bulk({ action: "delete_forever" })} />
      <ConfirmDialog isOpen={confirm === "read_all"} onOpenChange={(value) => !value && setConfirm(null)} tone="primary" title="Mark all as read?"
        body={`Every conversation in ${title}${q ? ` matching “${q}”` : ""} will be marked as read.`} confirmLabel="Mark all as read" onConfirm={markAllRead} />
    </div>
  );
}

"use client";

import { useMutation, useQueryClient, type InfiniteData, type QueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { toast } from "sonner";
import { errorMessage, mutate } from "@/services/api/client";
import type { ActionName, ActionRequest, ActionResult, ThreadDetail, ThreadPage, ThreadSummary } from "@/services/api/types";
import { ME_KEY } from "@/components/shell/session-provider";
import { mailKeys, type ThreadListParams } from "./keys";

type Thread = ThreadSummary;

const without = (ids: string[] | undefined, remove: string[]) => (ids ?? []).filter((id) => !remove.includes(id));
const withIds = (ids: string[] | undefined, add: string[]) => Array.from(new Set([...(ids ?? []), ...add]));

/** What an action does to one thread as seen from a list: the updated thread, or null when it leaves the list. */
export function applyAction(thread: Thread, req: ActionRequest, list?: Pick<ThreadListParams, "label" | "q">): Thread | null {
  const label = (list?.label ?? "").toUpperCase();
  const labels = req.label_ids ?? [];
  const leaves = (condition: boolean) => condition && !list?.q;
  switch (req.action) {
    case "read": return { ...thread, is_unread: false, label_ids: without(thread.label_ids, ["UNREAD"]) };
    case "unread": return { ...thread, is_unread: true, label_ids: withIds(thread.label_ids, ["UNREAD"]) };
    case "star": return { ...thread, is_starred: true, label_ids: withIds(thread.label_ids, ["STARRED"]) };
    case "unstar": return leaves(label === "STARRED") ? null : { ...thread, is_starred: false, label_ids: without(thread.label_ids, ["STARRED"]) };
    case "important": return { ...thread, is_important: true, label_ids: withIds(thread.label_ids, ["IMPORTANT"]) };
    case "not_important": return leaves(label === "IMPORTANT") ? null : { ...thread, is_important: false, label_ids: without(thread.label_ids, ["IMPORTANT"]) };
    case "archive": case "mute":
      return leaves(label === "INBOX") ? null : { ...thread, is_muted: req.action === "mute" || thread.is_muted, label_ids: without(thread.label_ids, ["INBOX"]) };
    case "unmute": return { ...thread, is_muted: false };
    case "move_to_inbox": case "untrash": case "not_spam":
      return leaves(label === "SPAM" || label === "TRASH") ? null : { ...thread, label_ids: withIds(without(thread.label_ids, ["SPAM", "TRASH"]), ["INBOX"]) };
    case "trash": return label === "TRASH" ? thread : null;
    case "spam": return label === "SPAM" ? thread : null;
    case "delete_forever": return null;
    case "add_labels": return { ...thread, label_ids: withIds(thread.label_ids, labels) };
    case "remove_labels": return leaves(labels.includes(list?.label ?? "")) ? null : { ...thread, label_ids: without(thread.label_ids, labels) };
    case "move_to_label": return leaves(label === "INBOX") ? null : { ...thread, label_ids: withIds(without(thread.label_ids, ["INBOX"]), labels) };
    case "snooze": return label === "SNOOZED" ? { ...thread, snoozed_until: req.until ?? null } : null;
    case "unsnooze": return leaves(label === "SNOOZED") ? null : { ...thread, snoozed_until: null };
    case "unassign": return leaves(label === "ASSIGNED") ? null : { ...thread, assignment: null };
    default: return thread;
  }
}

type ListSnapshot = [readonly unknown[], InfiniteData<ThreadPage> | undefined][];

function mapLists(client: QueryClient, fn: (thread: Thread, params: ThreadListParams) => Thread | null, ids?: Set<number>) {
  for (const [key, data] of client.getQueriesData<InfiniteData<ThreadPage>>({ queryKey: mailKeys.threadLists() })) {
    if (!data?.pages) continue;
    const params = (key[2] ?? {}) as ThreadListParams;
    let removed = 0;
    const pages = data.pages.map((page) => ({
      ...page,
      results: page.results.flatMap((thread) => {
        if (ids && !ids.has(thread.id)) return [thread];
        const next = fn(thread, params);
        if (!next) removed += 1;
        return next ? [next] : [];
      }),
    }));
    if (removed && pages[0] && pages[0].total !== null) pages[0] = { ...pages[0], total: Math.max(0, (pages[0].total ?? 0) - removed) };
    client.setQueryData(key, { ...data, pages });
  }
}

function refreshCounts(client: QueryClient) {
  client.invalidateQueries({ queryKey: ["mail", "labels"] });
  client.invalidateQueries({ queryKey: ME_KEY });
}

const DONE: Partial<Record<ActionName, (count: number) => string>> = {
  archive: (n) => (n === 1 ? "Conversation archived." : `${n} conversations archived.`),
  trash: (n) => (n === 1 ? "Conversation moved to Trash." : `${n} conversations moved to Trash.`),
  untrash: (n) => (n === 1 ? "Conversation restored." : `${n} conversations restored.`),
  spam: (n) => (n === 1 ? "Conversation marked as spam." : `${n} conversations marked as spam.`),
  not_spam: (n) => (n === 1 ? "Conversation moved to Inbox." : `${n} conversations moved to Inbox.`),
  move_to_inbox: (n) => (n === 1 ? "Conversation moved to Inbox." : `${n} conversations moved to Inbox.`),
  read: (n) => (n === 1 ? "Marked as read." : `${n} conversations marked as read.`),
  unread: (n) => (n === 1 ? "Marked as unread." : `${n} conversations marked as unread.`),
  move_to_label: (n) => (n === 1 ? "Conversation moved." : `${n} conversations moved.`),
  add_labels: (n) => (n === 1 ? "Label added." : `Labels added to ${n} conversations.`),
  remove_labels: (n) => (n === 1 ? "Label removed." : `Label removed from ${n} conversations.`),
  snooze: (n) => (n === 1 ? "Conversation snoozed." : `${n} conversations snoozed.`),
  unsnooze: () => "Snooze removed.",
  mute: (n) => (n === 1 ? "Conversation muted." : `${n} conversations muted.`),
  delete_forever: (n) => (n === 1 ? "Conversation deleted forever." : `${n} conversations deleted forever.`),
  assign: () => "Conversation assigned.",
  unassign: () => "Assignment removed.",
};

export type RunOptions = { quiet?: boolean; count?: number };

/**
 * Bulk thread actions with optimistic list updates, rollback on error and an undo toast. Returns `run(request)`.
 */
export function useThreadActions() {
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (req: ActionRequest) => mutate<ActionResult>("mail/actions/", "POST", req),
    onMutate: async (req) => {
      await client.cancelQueries({ queryKey: mailKeys.threadLists() });
      const lists = client.getQueriesData<InfiniteData<ThreadPage>>({ queryKey: mailKeys.threadLists() }) as ListSnapshot;
      const details = (req.thread_ids ?? []).map((id) => [id, client.getQueryData<ThreadDetail>(mailKeys.thread(id))] as const);
      const ids = req.select_all ? undefined : new Set(req.thread_ids ?? []);
      mapLists(client, (thread, params) => {
        if (req.select_all && (String(params.mailbox) !== String(req.select_all.mailbox) || params.label !== req.select_all.label)) return thread;
        return applyAction(thread, req, params);
      }, ids);
      for (const [id, detail] of details) {
        if (!detail) continue;
        const next = applyAction(detail, req);
        client.setQueryData<ThreadDetail>(mailKeys.thread(id), { ...detail, ...(next ?? {}) } as ThreadDetail);
      }
      return { lists, details };
    },
    onError: (error, _req, context) => {
      for (const [key, data] of context?.lists ?? []) client.setQueryData(key, data);
      for (const [id, detail] of context?.details ?? []) if (detail) client.setQueryData(mailKeys.thread(id), detail);
      toast.error(errorMessage(error));
    },
    onSuccess: (result) => {
      // Reconcile with the server's view of each thread (labels, unread state, assignment…).
      const fresh = new Map(result.threads.map((thread) => [thread.id, thread]));
      mapLists(client, (thread) => fresh.get(thread.id) ?? thread, new Set(fresh.keys()));
      for (const thread of result.threads) {
        const detail = client.getQueryData<ThreadDetail>(mailKeys.thread(thread.id));
        if (detail) client.setQueryData<ThreadDetail>(mailKeys.thread(thread.id), { ...detail, ...thread });
      }
      for (const id of result.deleted_ids) client.removeQueries({ queryKey: mailKeys.thread(id) });
      // Other lists (e.g. Trash after a delete) refetch when they are next opened; the visible one stays put.
      client.invalidateQueries({ queryKey: mailKeys.threadLists(), refetchType: "none" });
      refreshCounts(client);
    },
  });

  const undo = useCallback(async (token: string) => {
    try {
      await mutate<ActionResult>("mail/actions/undo/", "POST", { undo_token: token });
      await client.invalidateQueries({ queryKey: mailKeys.threadLists() });
      client.invalidateQueries({ queryKey: ["mail", "thread"] });
      refreshCounts(client);
      toast.success("Action undone.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }, [client]);

  const run = useCallback(async (req: ActionRequest, options: RunOptions = {}) => {
    const count = options.count ?? req.thread_ids?.length ?? 0;
    const result = await mutation.mutateAsync(req).catch(() => null);
    if (!result) return null;
    const message = DONE[req.action]?.(count);
    if (message && !options.quiet) {
      const token = result.undo_token;
      toast(message, token ? { action: { label: "Undo", onClick: () => undo(token) }, duration: 7000 } : { duration: 4000 });
    }
    return result;
  }, [mutation, undo]);

  return { run, isPending: mutation.isPending };
}

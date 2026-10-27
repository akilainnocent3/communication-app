"use client";

import { useMutation, useQueryClient, type InfiniteData, type QueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { toast } from "sonner";
import { ME_KEY } from "@/components/shell/session-provider";
import { m } from "@/i18n";
import { errorMessage, mutate } from "@/services/api/client";
import type { ConversationDetail, ConversationPage, ConversationSummary, SmsActionName, SmsActionRequest, SmsActionResult } from "@/services/api/types";
import { smsKeys, type ConversationListParams } from "./keys";

type Conversation = ConversationSummary;

/** Undo = the inverse action (the server keeps no undo tokens for SMS). */
export const INVERSE: Partial<Record<SmsActionName, SmsActionName>> = {
  read: "unread", unread: "read", pin: "unpin", unpin: "pin", archive: "unarchive", unarchive: "archive", mute: "unmute", unmute: "mute",
  spam: "not_spam", not_spam: "spam", done: "reopen", reopen: "done", star: "unstar", unstar: "star", block: "unblock", unblock: "block",
};

/** What an action does to a conversation as seen from a list: the updated row, or null when it leaves the list. */
export function applyAction(row: Conversation, req: SmsActionRequest, list?: Pick<ConversationListParams, "folder">): Conversation | null {
  const folder = list?.folder;
  switch (req.action) {
    case "read": return folder === "unread" ? null : { ...row, unread_count: 0 };
    case "unread": return { ...row, unread_count: Math.max(1, row.unread_count) };
    case "pin": return { ...row, is_pinned: true };
    case "unpin": return { ...row, is_pinned: false };
    case "star": return { ...row, is_starred: true };
    case "unstar": return folder === "starred" ? null : { ...row, is_starred: false };
    case "archive": return folder === "inbox" || folder === "awaiting" ? null : { ...row, is_archived: true };
    case "unarchive": return folder === "archived" ? null : { ...row, is_archived: false };
    case "mute": return { ...row, is_muted: true };
    case "unmute": return { ...row, is_muted: false };
    case "spam": case "block": return folder === "spam" ? { ...row, is_spam: true } : null;
    case "not_spam": case "unblock": return folder === "spam" ? null : { ...row, is_spam: false };
    case "done": return folder === "awaiting" ? null : { ...row, state: "done" };
    case "reopen": return { ...row, state: "open" };
    case "unassign": return folder === "assigned" ? null : { ...row, assigned_to: null };
    default: return row;
  }
}

type ListSnapshot = [readonly unknown[], InfiniteData<ConversationPage> | undefined][];

function mapLists(client: QueryClient, fn: (row: Conversation, params: ConversationListParams) => Conversation | null, ids: Set<number>) {
  for (const [key, data] of client.getQueriesData<InfiniteData<ConversationPage>>({ queryKey: smsKeys.conversationLists() })) {
    if (!data?.pages) continue;
    const params = (key[2] ?? {}) as ConversationListParams;
    let removed = 0;
    const pages = data.pages.map((page) => ({
      ...page,
      results: page.results.flatMap((row) => {
        if (!ids.has(row.id)) return [row];
        const next = fn(row, params);
        if (!next) removed += 1;
        return next ? [next] : [];
      }),
    }));
    if (removed && pages[0] && pages[0].total !== null && pages[0].total !== undefined) pages[0] = { ...pages[0], total: Math.max(0, pages[0].total - removed) };
    client.setQueryData(key, { ...data, pages });
  }
}

export type RunOptions = { quiet?: boolean; count?: number; undoable?: boolean };

/** Conversation actions with optimistic list updates, rollback on error and an undo toast (inverse action). */
export function useConversationActions() {
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (req: SmsActionRequest) => mutate<SmsActionResult>("sms/conversations/actions/", "POST", req),
    onMutate: async (req) => {
      await client.cancelQueries({ queryKey: smsKeys.conversationLists() });
      const lists = client.getQueriesData<InfiniteData<ConversationPage>>({ queryKey: smsKeys.conversationLists() }) as ListSnapshot;
      const details = req.conversation_ids.map((id) => [id, client.getQueryData<ConversationDetail>(smsKeys.conversation(id))] as const);
      mapLists(client, (row, params) => applyAction(row, req, params), new Set(req.conversation_ids));
      for (const [id, detail] of details) {
        if (!detail) continue;
        const next = applyAction(detail, req);
        client.setQueryData<ConversationDetail>(smsKeys.conversation(id), { ...detail, ...(next ?? {}) } as ConversationDetail);
      }
      return { lists, details };
    },
    onError: (error, _req, context) => {
      for (const [key, data] of context?.lists ?? []) client.setQueryData(key, data);
      for (const [id, detail] of context?.details ?? []) if (detail) client.setQueryData(smsKeys.conversation(id), detail);
      toast.error(errorMessage(error));
    },
    onSuccess: (result) => {
      const fresh = new Map(result.conversations.map((row) => [row.id, row]));
      mapLists(client, (row) => fresh.get(row.id) ?? row, new Set(fresh.keys()));
      for (const row of result.conversations) {
        const detail = client.getQueryData<ConversationDetail>(smsKeys.conversation(row.id));
        if (detail) client.setQueryData<ConversationDetail>(smsKeys.conversation(row.id), { ...detail, ...row });
      }
      client.invalidateQueries({ queryKey: smsKeys.conversationLists(), refetchType: "none" });
      client.invalidateQueries({ queryKey: ME_KEY });
    },
  });

  const run = useCallback(async (req: SmsActionRequest, options: RunOptions = {}): Promise<SmsActionResult | null> => {
    const result = await mutation.mutateAsync(req).catch(() => null);
    if (!result || options.quiet) return result;
    const inverse = INVERSE[req.action];
    const message = m.sms.done[req.action as keyof typeof m.sms.done];
    if (message) {
      toast(message, inverse && options.undoable !== false ? {
        action: { label: m.common.undo, onClick: () => { mutation.mutateAsync({ ...req, action: inverse }).then(() => toast.success("Action undone.")).catch(() => undefined); } },
        duration: 7000,
      } : { duration: 4000 });
    }
    return result;
  }, [mutation]);

  return { run, isPending: mutation.isPending };
}

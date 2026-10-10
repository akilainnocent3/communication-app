"use client";

import { keepPreviousData, useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSession } from "@/components/shell/session-provider";
import { query, request } from "@/services/api/client";
import type {
  Assignee, Draft, Label, Mailbox, MailboxSummary, Note, Queued, SendAs, Stats, Template, ThreadDetail, ThreadPage,
} from "@/services/api/types";
import { mailKeys, type ThreadListParams } from "./keys";
import { setMailboxScope, useMailboxScopeRaw, type MailboxScope } from "../state";

/** Mailboxes from GET /auth/me/ (cheap; refreshed with the session). */
export function useMailboxSummaries(): MailboxSummary[] {
  const { me } = useSession();
  return me?.platform_data.gmail?.mailboxes ?? [];
}

/** The selected scope, falling back to "all" when the stored mailbox is no longer accessible. */
export function useMailboxScope(): [MailboxScope, (scope: MailboxScope) => void] {
  const raw = useMailboxScopeRaw();
  const mailboxes = useMailboxSummaries();
  const { me } = useSession();
  const valid = raw === "all" || !me || mailboxes.some((box) => box.id === raw) ? raw : "all";
  return [valid, setMailboxScope];
}

export function useCurrentMailbox(): MailboxSummary | undefined {
  const [scope] = useMailboxScope();
  const mailboxes = useMailboxSummaries();
  return scope === "all" ? undefined : mailboxes.find((box) => box.id === scope);
}

export function useMailboxes() {
  return useQuery({ queryKey: mailKeys.mailboxes(), queryFn: () => request<Mailbox[]>("mail/mailboxes/"), staleTime: 15_000 });
}

export function useMailbox(id: number | undefined) {
  return useQuery({ queryKey: mailKeys.mailbox(id ?? 0), queryFn: () => request<Mailbox>(`mail/mailboxes/${id}/`), enabled: !!id });
}

export function useLabels(mailbox: number | undefined) {
  return useQuery({
    queryKey: mailKeys.labels(mailbox ?? 0),
    queryFn: () => request<Label[]>(`mail/labels/${query({ mailbox })}`),
    enabled: !!mailbox,
    staleTime: 30_000,
  });
}

export function threadListPath(params: ThreadListParams, cursor?: string | null) {
  return `mail/threads/${query({ ...params, mailbox: String(params.mailbox), cursor })}`;
}

export function useThreadList(params: ThreadListParams) {
  return useInfiniteQuery({
    queryKey: mailKeys.threads(params),
    queryFn: ({ pageParam, signal }) => request<ThreadPage>(threadListPath(params, pageParam), { signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    staleTime: 20_000,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}

export function threadPath(id: number, peek = false) {
  return `mail/threads/${id}/${peek ? "?peek=1" : ""}`;
}

export function useThread(id: number | null) {
  return useQuery({
    queryKey: mailKeys.thread(id ?? 0),
    queryFn: () => request<ThreadDetail>(threadPath(id!)),
    enabled: !!id,
    staleTime: 60_000,
  });
}

/** Hovering a row warms the thread (peek: does not mark it read or write an audit event). */
export function usePrefetchThread() {
  const client = useQueryClient();
  return (id: number) =>
    client.prefetchQuery({ queryKey: ["mail", "thread-peek", id], queryFn: () => request<ThreadDetail>(threadPath(id, true)), staleTime: 60_000 });
}

export function useNotes(thread: number) {
  return useQuery({ queryKey: mailKeys.notes(thread), queryFn: () => request<Note[]>(`mail/threads/${thread}/notes/`) });
}

export function useDrafts() {
  return useQuery({ queryKey: mailKeys.drafts(), queryFn: () => request<Draft[]>("mail/drafts/"), staleTime: 10_000 });
}

export function useScheduled() {
  return useQuery({ queryKey: mailKeys.scheduled(), queryFn: () => request<Queued[]>("mail/scheduled/"), staleTime: 10_000 });
}

export function useTemplates() {
  return useQuery({ queryKey: mailKeys.templates(), queryFn: () => request<Template[]>("mail/templates/"), staleTime: 60_000 });
}

export function useStats(scope: MailboxScope, days: number) {
  return useQuery({
    queryKey: mailKeys.stats(scope, days),
    queryFn: () => request<Stats>(`mail/stats/${query({ range: days, mailbox: scope === "all" ? undefined : scope })}`),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
}

export function useAssignees(mailbox: number | undefined) {
  return useQuery({
    queryKey: mailKeys.assignees(mailbox ?? 0),
    queryFn: () => request<Assignee[]>(`mail/assignees/${query({ mailbox })}`),
    enabled: !!mailbox,
    staleTime: 5 * 60_000,
  });
}

export function useSendAs(mailbox: number | undefined) {
  return useQuery({ queryKey: mailKeys.sendAs(mailbox ?? 0), queryFn: () => request<SendAs[]>(`mail/settings/${mailbox}/send-as/`), enabled: !!mailbox, staleTime: 5 * 60_000 });
}

/** Unread counts for the sidebar badges (Inbox, Drafts, Spam). */
export function useMailBadges(): Record<string, number> {
  const [scope] = useMailboxScope();
  const mailboxes = useMailboxSummaries();
  const labels = useLabels(scope === "all" ? undefined : scope);
  const drafts = useDrafts();
  return useMemo(() => {
    const byId = new Map((labels.data ?? []).map((label) => [label.label_id, label]));
    const inbox = scope === "all" ? mailboxes.reduce((sum, box) => sum + box.unread, 0) : byId.get("INBOX")?.threads_unread ?? mailboxes.find((box) => box.id === scope)?.unread ?? 0;
    const draftCount = (drafts.data ?? []).filter((draft) => scope === "all" || draft.mailbox === scope).length;
    const result: Record<string, number> = { inbox, drafts: draftCount, spam: byId.get("SPAM")?.threads_unread ?? 0 };
    for (const label of labels.data ?? []) if (label.type === "user") result[`label:${label.label_id}`] = label.threads_unread ?? 0;
    return result;
  }, [labels.data, drafts.data, mailboxes, scope]);
}

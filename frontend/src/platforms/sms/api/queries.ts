"use client";

import { keepPreviousData, useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSession } from "@/components/shell/session-provider";
import { query, request } from "@/services/api/client";
import type {
  ContactPage, ConversationDetail, ConversationPage, Device, DeviceDetail, DeviceSummary, Enrollment, HeartbeatHistory, OutboxItem, QuickReply,
  SensitiveRule, SmsAssignee, SmsMessagePage, SmsNote, SmsSettings, SmsStats,
} from "@/services/api/types";
import { setDeviceScope, useDeviceScopeRaw, type DeviceScope } from "../state";
import { smsKeys, type ConversationListParams } from "./keys";

/** Freshness: polling pauses while the tab is hidden (TanStack's default refetchIntervalInBackground: false). */
export const POLL = { list: 10_000, chat: 5_000, device: 30_000 } as const;

/** Phones from GET /auth/me/ (cheap; refreshed with the session). */
export function useDeviceSummaries(): DeviceSummary[] {
  const { me } = useSession();
  return me?.platform_data.sms?.devices ?? [];
}

/** The selected scope, falling back to "all" when the stored phone is no longer accessible. */
export function useDeviceScope(): [DeviceScope, (scope: DeviceScope) => void] {
  const raw = useDeviceScopeRaw();
  const devices = useDeviceSummaries();
  const { me } = useSession();
  const valid = raw === "all" || !me || devices.some((device) => device.id === raw) ? raw : "all";
  return [valid, setDeviceScope];
}

export function useCurrentDevice(): DeviceSummary | undefined {
  const [scope] = useDeviceScope();
  const devices = useDeviceSummaries();
  return scope === "all" ? undefined : devices.find((device) => device.id === scope);
}

export function useDevices(includeRevoked = false) {
  return useQuery({
    queryKey: [...smsKeys.devices(), includeRevoked],
    queryFn: () => request<Device[]>(`sms/devices/${includeRevoked ? "?include_revoked=1" : ""}`),
    staleTime: 10_000,
    refetchInterval: POLL.device,
  });
}

export function useDevice(id: string | undefined) {
  return useQuery({ queryKey: smsKeys.device(id ?? ""), queryFn: () => request<DeviceDetail>(`sms/devices/${id}/`), enabled: !!id, refetchInterval: POLL.device });
}

export function useHeartbeats(id: string) {
  return useQuery({ queryKey: smsKeys.heartbeats(id), queryFn: () => request<HeartbeatHistory[]>(`sms/devices/${id}/heartbeats/`), refetchInterval: 60_000 });
}

export function useEnrollments(enabled = true) {
  return useQuery({ queryKey: smsKeys.enrollments(), queryFn: () => request<Enrollment[]>("sms/enrollments/"), enabled, staleTime: 10_000 });
}

export function conversationListPath(params: ConversationListParams, cursor?: string | null) {
  return `sms/conversations/${query({ ...params, device: String(params.device), cursor })}`;
}

export function useConversationList(params: ConversationListParams) {
  return useInfiniteQuery({
    queryKey: smsKeys.conversations(params),
    queryFn: ({ pageParam, signal }) => request<ConversationPage>(conversationListPath(params, pageParam), { signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    staleTime: 5_000,
    refetchInterval: POLL.list,
    placeholderData: keepPreviousData,
  });
}

export function conversationPath(id: number, peek = false) {
  return `sms/conversations/${id}/${peek ? "?peek=1" : ""}`;
}

/**
 * Opening a conversation is audited and marks it read (once per open). The 5 s refresh afterwards peeks, which does
 * neither again, and writes into the same cache entry.
 */
export function useConversation(id: number | null) {
  const client = useQueryClient();
  const open = useQuery({
    queryKey: smsKeys.conversation(id ?? 0),
    queryFn: () => request<ConversationDetail>(conversationPath(id!)),
    enabled: !!id,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  useQuery({
    queryKey: [...smsKeys.conversation(id ?? 0), "peek"],
    queryFn: async () => {
      const data = await request<ConversationDetail>(conversationPath(id!, true));
      client.setQueryData(smsKeys.conversation(id!), data);
      return data;
    },
    enabled: !!id && open.isSuccess,
    initialData: open.data,
    initialDataUpdatedAt: open.dataUpdatedAt,
    refetchInterval: POLL.chat,
    staleTime: POLL.chat,
  });
  return open;
}

export function useMessages(conversation: number) {
  return useInfiniteQuery({
    queryKey: smsKeys.messages(conversation),
    queryFn: ({ pageParam, signal }) => request<SmsMessagePage>(`sms/conversations/${conversation}/messages/${query({ cursor: pageParam })}`, { signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    refetchInterval: POLL.chat,
  });
}

export function useMessageSearch(conversation: number, q: string) {
  return useQuery({
    queryKey: smsKeys.messageSearch(conversation, q),
    queryFn: () => request<SmsMessagePage>(`sms/conversations/${conversation}/messages/${query({ q })}`),
    enabled: q.trim().length >= 2,
    staleTime: 30_000,
  });
}

export function useNotes(conversation: number) {
  return useQuery({ queryKey: smsKeys.notes(conversation), queryFn: () => request<SmsNote[]>(`sms/conversations/${conversation}/notes/`) });
}

export function useOutbox(view: "pending" | "problems" | "scheduled", device: DeviceScope) {
  return useQuery({
    queryKey: smsKeys.outbox(view, device),
    queryFn: () => request<OutboxItem[]>(`sms/outbox/${query({ view, device: device === "all" ? undefined : device })}`),
    refetchInterval: POLL.list,
  });
}

export function useSmsStats(device: DeviceScope, days: number, sim?: number) {
  return useQuery({
    queryKey: smsKeys.stats(device, days, sim),
    queryFn: () => request<SmsStats>(`sms/stats/${query({ range: days, device: device === "all" ? undefined : device, sim })}`),
    staleTime: 30_000,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}

export function useContacts(device: DeviceScope, q: string, blocked?: boolean) {
  return useInfiniteQuery({
    queryKey: smsKeys.contacts(device, q, blocked),
    queryFn: ({ pageParam }) => request<ContactPage>(`sms/contacts/${query({ device: device === "all" ? undefined : device, q: q || undefined, blocked, cursor: pageParam })}`),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    placeholderData: keepPreviousData,
  });
}

export function useQuickReplies(device: DeviceScope) {
  return useQuery({ queryKey: smsKeys.quickReplies(device), queryFn: () => request<QuickReply[]>(`sms/quick-replies/${query({ device: device === "all" ? undefined : device })}`), staleTime: 60_000 });
}

export function useRules() {
  return useQuery({ queryKey: smsKeys.rules(), queryFn: () => request<SensitiveRule[]>("sms/rules/") });
}

export function useSmsSettings() {
  return useQuery({ queryKey: smsKeys.settings(), queryFn: () => request<SmsSettings>("sms/settings/") });
}

export function useAssignees(device: string | undefined) {
  return useQuery({ queryKey: smsKeys.assignees(device ?? ""), queryFn: () => request<SmsAssignee[]>(`sms/assignees/${query({ device })}`), enabled: !!device, staleTime: 5 * 60_000 });
}

/** Sidebar badges: unread (inbox), awaiting reply and outbox problems. */
export function useSmsBadges(): Record<string, number> {
  const [scope] = useDeviceScope();
  const devices = useDeviceSummaries();
  const problems = useOutbox("problems", scope);
  const pending = useOutbox("pending", scope);
  return useMemo(() => {
    const inScope = scope === "all" ? devices : devices.filter((device) => device.id === scope);
    return {
      inbox: inScope.reduce((sum, device) => sum + device.unread, 0),
      outbox: (problems.data?.length ?? 0) + (pending.data?.length ?? 0),
      attention: inScope.filter((device) => device.attention.length > 0).length,
    };
  }, [devices, scope, problems.data, pending.data]);
}

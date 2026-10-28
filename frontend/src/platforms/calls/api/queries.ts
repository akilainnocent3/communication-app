"use client";

import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSession } from "@/components/shell/session-provider";
import { query, request } from "@/services/api/client";
import type {
  CallBadges, CallDetail, CallDevice, CallDeviceAccess, CallHistoryItem, CallLive, CallOutcome, CallPage, CallSettings, CallStats, Callback, CallsDeviceSummary,
  CarrierTariff, CustomerDetail, CustomerPage, OfficeHours,
} from "@/services/api/types";
import { setCallsScope, useCallsScopeRaw, type CallsScope } from "../state";
import { callsKeys, type CallListParams, type CallbackView } from "./keys";

/** Freshness by polling, paused while the tab is hidden (as SMS, decision 28). Live board: every 3 s. */
export const POLL = { list: 10_000, live: 3_000, detail: 10_000, badges: 30_000 } as const;

export function useCallsDevices(): CallsDeviceSummary[] {
  const { me } = useSession();
  return me?.platform_data.calls?.devices ?? [];
}

export function useCallsScope(): [CallsScope, (scope: CallsScope) => void] {
  const raw = useCallsScopeRaw();
  const devices = useCallsDevices();
  const { me } = useSession();
  const valid = raw === "all" || !me || devices.some((device) => device.id === raw) ? raw : "all";
  return [valid, setCallsScope];
}

export function useCurrentCallsDevice(): CallsDeviceSummary | undefined {
  const [scope] = useCallsScope();
  const devices = useCallsDevices();
  return scope === "all" ? undefined : devices.find((device) => device.id === scope);
}

export const scopeParam = (device: CallsScope) => (device === "all" ? undefined : device);

export function callListPath(params: CallListParams, cursor?: string | null) {
  return `calls/calls/${query({ ...params, device: params.device, cursor })}`;
}

export function useCallList(params: CallListParams) {
  return useInfiniteQuery({
    queryKey: callsKeys.list(params),
    queryFn: ({ pageParam, signal }) => request<CallPage>(callListPath(params, pageParam), { signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    staleTime: 5_000,
    refetchInterval: POLL.list,
    placeholderData: keepPreviousData,
  });
}

/** Opening a call is audited once; the refresh afterwards peeks. */
export function useCall(id: number | null) {
  return useQuery({
    queryKey: callsKeys.call(id ?? 0),
    queryFn: async () => {
      const opened = sessionOpened.has(id!);
      sessionOpened.add(id!);
      return request<CallDetail>(`calls/calls/${id}/${opened ? "?peek=1" : ""}`);
    },
    enabled: !!id,
    refetchInterval: POLL.detail,
  });
}
const sessionOpened = new Set<number>();

export function useCallbacks(view: CallbackView, device: CallsScope) {
  return useQuery({
    queryKey: callsKeys.callbacks(view, device),
    queryFn: () => request<Callback[]>(`calls/callbacks/${query({ view, device: scopeParam(device) })}`),
    refetchInterval: POLL.list,
    placeholderData: keepPreviousData,
  });
}

export function useLive() {
  return useQuery({ queryKey: callsKeys.live(), queryFn: () => request<CallLive>("calls/live/"), refetchInterval: POLL.live });
}

export function useCallStats(device: CallsScope, days: number, sim?: number) {
  return useQuery({
    queryKey: callsKeys.stats(device, days, sim),
    queryFn: () => request<CallStats>(`calls/stats/${query({ range: days, device: scopeParam(device), sim })}`),
    staleTime: 30_000,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}

export function useCallDevices(candidates = false, enabled = true) {
  return useQuery({ queryKey: callsKeys.devices(candidates), queryFn: () => request<CallDevice[]>(`calls/devices/${candidates ? "?candidates=1" : ""}`), enabled, refetchInterval: 30_000 });
}

export function useCallAccess(id: string) {
  return useQuery({ queryKey: callsKeys.access(id), queryFn: () => request<CallDeviceAccess[]>(`calls/devices/${id}/access/`) });
}

export function useCustomers(q: string, tag?: string) {
  return useInfiniteQuery({
    queryKey: callsKeys.customers(q, tag),
    queryFn: ({ pageParam }) => request<CustomerPage>(`calls/customers/${query({ q: q || undefined, tag, cursor: pageParam })}`),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    placeholderData: keepPreviousData,
  });
}

export function useCustomer(id: number) {
  return useQuery({ queryKey: callsKeys.customer(id), queryFn: () => request<CustomerDetail>(`calls/customers/${id}/`) });
}

export function useCustomerTimeline(id: number) {
  return useQuery({ queryKey: callsKeys.timeline(id), queryFn: () => request<CallHistoryItem[]>(`calls/customers/${id}/timeline/`) });
}

export function useOutcomes() {
  return useQuery({ queryKey: callsKeys.outcomes(), queryFn: () => request<CallOutcome[]>("calls/outcomes/"), staleTime: 60_000 });
}

export function useCallSettings() {
  return useQuery({ queryKey: callsKeys.settings(), queryFn: () => request<CallSettings>("calls/settings/") });
}

export function useOfficeHours() {
  return useQuery({ queryKey: callsKeys.hours(), queryFn: () => request<OfficeHours[]>("calls/office-hours/") });
}

export function useTariffs() {
  return useQuery({ queryKey: callsKeys.tariffs(), queryFn: () => request<CarrierTariff[]>("calls/tariffs/") });
}

/** Sidebar badges: unreturned missed calls and open call-backs (in the selected scope). */
export function useCallsBadges(): Record<string, number> {
  const [scope] = useCallsScope();
  const devices = useCallsDevices();
  const badges = useQuery({ queryKey: callsKeys.badges(scope), queryFn: () => request<CallBadges>(`calls/badges/${query({ device: scopeParam(scope) })}`), refetchInterval: POLL.badges });
  return useMemo(() => {
    const inScope = scope === "all" ? devices : devices.filter((device) => device.id === scope);
    return {
      unreturned: badges.data?.unreturned ?? 0,
      callbacks: badges.data?.open_callbacks ?? 0,
      mine: badges.data?.my_callbacks ?? 0,
      attention: inScope.filter((device) => device.attention.length > 0).length,
    };
  }, [badges.data, devices, scope]);
}

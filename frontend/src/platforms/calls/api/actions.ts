"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { errorMessage, mutate } from "@/services/api/client";
import type { CallAnnotation, CallDevice, Callback, CustomerDetail } from "@/services/api/types";
import { callsKeys } from "./keys";

function useInvalidate() {
  const client = useQueryClient();
  return (...keys: readonly (readonly unknown[])[]) => keys.forEach((key) => client.invalidateQueries({ queryKey: key }));
}

export type NewCallback = { device: string; number?: string; call?: number | null; customer?: number | null; due_at?: string | null; priority?: string; reason?: string };

export function useCreateCallback() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: NewCallback) => mutate<Callback>("calls/callbacks/", "POST", body),
    onSuccess: () => { invalidate(callsKeys.callbackLists(), ["calls", "badges"], callsKeys.lists()); toast.success("Call-back sent to the phone"); },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useCallbackAction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, action, body }: { id: number; action: "cancel" | "update"; body?: Record<string, unknown> }) =>
      action === "cancel" ? mutate<Callback>(`calls/callbacks/${id}/cancel/`, "POST") : mutate<Callback>(`calls/callbacks/${id}/`, "PATCH", body),
    onSuccess: () => invalidate(callsKeys.callbackLists(), ["calls", "badges"]),
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useBulkCallbacks() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { ids: number[]; action: "assign" | "cancel" | "done"; device?: string }) => mutate<Callback[]>("calls/callbacks/bulk/", "POST", body),
    onSuccess: (rows) => { invalidate(callsKeys.callbackLists(), ["calls", "badges"]); toast.success(`${rows.length} call-backs updated`); },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useAnnotate(callId: number) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { outcome?: number | null; note?: string; tags?: string[] }) => mutate<CallAnnotation>(`calls/calls/${callId}/annotations/`, "POST", body),
    onSuccess: () => { invalidate(callsKeys.call(callId), callsKeys.lists()); toast.success("Note saved"); },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useDeleteAnnotation(callId: number) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => mutate<void>(`calls/annotations/${id}/`, "DELETE"),
    onSuccess: () => invalidate(callsKeys.call(callId), callsKeys.lists()),
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useEnableCalls() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => mutate<CallDevice>(`calls/devices/${id}/enable/`, "POST", { enabled }),
    onSuccess: (device) => { invalidate(["calls", "devices"], ["auth", "me"]); toast.success(device.calls_enabled ? `Calls enabled on ${device.name}` : `Calls switched off on ${device.name}`); },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useSaveCustomer(id?: number) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => (id ? mutate<CustomerDetail>(`calls/customers/${id}/`, "PATCH", body) : mutate<CustomerDetail>("calls/customers/", "POST", body)),
    onSuccess: () => { invalidate(["calls", "customers"], ["calls", "customer"]); toast.success("Customer saved"); },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useMergeCustomers() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { target: number; sources: number[] }) => mutate<CustomerDetail>("calls/customers/merge/", "POST", body),
    onSuccess: () => { invalidate(["calls", "customers"], ["calls", "customer"], ["calls", "timeline"]); toast.success("Customers merged"); },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

/** Generic save for the tool pages (outcomes, tariffs, settings, office hours). */
export function useCallsWrite<T>(key: readonly unknown[]) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ path, method, body }: { path: string; method: "POST" | "PUT" | "PATCH" | "DELETE"; body?: unknown }) => mutate<T>(path, method, body),
    onSuccess: () => invalidate(key),
    onError: (error) => toast.error(errorMessage(error)),
  });
}

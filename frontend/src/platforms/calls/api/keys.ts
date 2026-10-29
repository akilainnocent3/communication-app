import type { CallsScope } from "../state";

export type CallFolder = "all" | "missed" | "unreturned" | "incoming" | "outgoing" | "after_hours";
export type CallbackView = "open" | "mine" | "done";

export type CallListParams = {
  device: CallsScope;
  folder: CallFolder;
  q?: string;
  sim?: number;
  result?: string;
  after?: string;
  before?: string;
  min_duration?: number;
  outcome?: number;
};

export const callsKeys = {
  all: ["calls"] as const,
  lists: () => ["calls", "list"] as const,
  list: (params: CallListParams) => ["calls", "list", params] as const,
  call: (id: number) => ["calls", "call", id] as const,
  callbacks: (view: string, device: CallsScope) => ["calls", "callbacks", view, device] as const,
  callbackLists: () => ["calls", "callbacks"] as const,
  live: () => ["calls", "live"] as const,
  stats: (device: CallsScope, days: number, sim?: number) => ["calls", "stats", device, days, sim ?? null] as const,
  badges: (device: CallsScope) => ["calls", "badges", device] as const,
  devices: (candidates = false) => ["calls", "devices", candidates] as const,
  enrollment: (id: number) => ["calls", "enrollments", id] as const,
  access: (id: string) => ["calls", "access", id] as const,
  customers: (q: string, tag?: string) => ["calls", "customers", q, tag ?? null] as const,
  customer: (id: number) => ["calls", "customer", id] as const,
  timeline: (id: number) => ["calls", "timeline", id] as const,
  outcomes: () => ["calls", "outcomes"] as const,
  settings: () => ["calls", "settings"] as const,
  hours: () => ["calls", "hours"] as const,
  tariffs: () => ["calls", "tariffs"] as const,
};

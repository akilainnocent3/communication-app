import type { DeviceScope } from "../state";

export type SmsFolder = "inbox" | "unread" | "awaiting" | "assigned" | "starred" | "archived" | "spam";

export type ConversationListParams = {
  device: DeviceScope;
  folder: SmsFolder;
  q?: string;
  unread?: boolean;
  direction?: "in" | "out";
  sim?: number;
  has_mms?: boolean;
};

export const smsKeys = {
  all: ["sms"] as const,
  devices: () => ["sms", "devices"] as const,
  device: (id: string) => ["sms", "devices", id] as const,
  heartbeats: (id: string) => ["sms", "heartbeats", id] as const,
  access: (id: string) => ["sms", "access", id] as const,
  enrollments: () => ["sms", "enrollments"] as const,
  enrollment: (id: number) => ["sms", "enrollments", id] as const,
  conversationLists: () => ["sms", "conversations"] as const,
  conversations: (params: ConversationListParams) => ["sms", "conversations", params] as const,
  conversation: (id: number) => ["sms", "conversation", id] as const,
  messages: (id: number) => ["sms", "messages", id] as const,
  messageSearch: (id: number, q: string) => ["sms", "message-search", id, q] as const,
  notes: (id: number) => ["sms", "notes", id] as const,
  outbox: (view: string, device: DeviceScope) => ["sms", "outbox", view, device] as const,
  stats: (device: DeviceScope, days: number, sim?: number) => ["sms", "stats", device, days, sim ?? null] as const,
  contacts: (device: DeviceScope, q: string, blocked?: boolean) => ["sms", "contacts", device, q, blocked ?? null] as const,
  quickReplies: (device: DeviceScope) => ["sms", "quick-replies", device] as const,
  rules: () => ["sms", "rules"] as const,
  settings: () => ["sms", "settings"] as const,
  assignees: (device: string) => ["sms", "assignees", device] as const,
};

import type { MailboxScope } from "../state";

export type ThreadListParams = {
  mailbox: MailboxScope;
  label?: string;
  category?: string;
  q?: string;
  unread?: boolean;
  starred?: boolean;
  has_attachment?: boolean;
};

export const mailKeys = {
  all: ["mail"] as const,
  mailboxes: () => ["mail", "mailboxes"] as const,
  mailbox: (id: number) => ["mail", "mailboxes", id] as const,
  labels: (mailbox: number) => ["mail", "labels", mailbox] as const,
  threadLists: () => ["mail", "threads"] as const,
  threads: (params: ThreadListParams) => ["mail", "threads", params] as const,
  thread: (id: number) => ["mail", "thread", id] as const,
  notes: (thread: number) => ["mail", "notes", thread] as const,
  drafts: () => ["mail", "drafts"] as const,
  scheduled: () => ["mail", "scheduled"] as const,
  templates: () => ["mail", "templates"] as const,
  stats: (scope: MailboxScope, days: number) => ["mail", "stats", scope, days] as const,
  assignees: (mailbox: number) => ["mail", "assignees", mailbox] as const,
  sendAs: (mailbox: number) => ["mail", "send-as", mailbox] as const,
  vacation: (mailbox: number) => ["mail", "vacation", mailbox] as const,
  filters: (mailbox: number) => ["mail", "filters", mailbox] as const,
  invites: (mailbox: number) => ["mail", "invites", mailbox] as const,
  access: (mailbox: number) => ["mail", "access", mailbox] as const,
  status: (mailbox: number) => ["mail", "status", mailbox] as const,
};

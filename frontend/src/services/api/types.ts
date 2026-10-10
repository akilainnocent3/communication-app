/**
 * Friendly names for the generated OpenAPI types (`npm run gen:api` regenerates schema.d.ts from
 * contracts/openapi.yaml). Never hand-write API shapes here: alias the generated ones.
 */
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["Me"] & { platform_data: { gmail?: { mailboxes: MailboxSummary[] } } };
export type MeUser = S["MeUser"];
export type Preferences = {
  shortcuts: boolean;
  density: "comfortable" | "compact";
  reading_pane: "right" | "none";
  swipe_right: SwipeAction;
  swipe_left: SwipeAction;
  undo_send_seconds: 0 | 5 | 10 | 20 | 30;
};
export type SwipeAction = "archive" | "trash" | "read" | "none";
export type Platform = S["Platform"];
export type Office = S["Office"];
export type User = S["User"];
export type Role = S["Role"];
export type PermissionItem = S["PermissionItem"];
export type AuditEvent = S["AuditEvent"];
export type AuditPage = S["AuditPage"];

export type Mailbox = S["Mailbox"];
export type MailboxStatusName = Mailbox["status"];
export type MailboxPermissions = S["MailboxPermissions"];
export type Capabilities = S["Capabilities"];
export type MailboxCreated = S["MailboxCreated"];
export type Detection = S["Detection"];
export type Invite = S["Invite"];
export type InviteCreated = S["InviteCreated"];
export type MailboxStatus = S["MailboxStatus"];
export type ImapSettings = S["ImapSettingsRequest"];
export type ImapTestResult = S["ImapTestResult"] & { imap: { ok: boolean; message: string }; smtp: { ok: boolean; message: string } };
export type AccessEntry = S["AccessEntry"];
export type PublicInvite = S["PublicInvite"];

/** Mailbox entry in GET /auth/me/ (platform_data.gmail.mailboxes) used by the switcher. */
export type MailboxSummary = {
  id: number;
  email: string;
  name: string;
  office: { id: number; name: string; colour: string };
  colour: string;
  provider: Mailbox["provider"];
  status: MailboxStatusName;
  unread: number;
  permissions: MailboxPermissions;
};

export type Label = S["Label"];
export type LabelChip = S["LabelChip"];
export type ThreadSummary = S["ThreadSummary"];
export type ThreadDetail = S["ThreadDetail"];
export type ThreadPage = S["ThreadPage"];
export type Message = S["Message"];
export type Address = S["Address"];
export type Attachment = S["Attachment"];
export type Participant = S["Participant"];
export type ActionResult = S["ActionResult"];
export type ActionName = S["ActionRequestRequest"]["action"];
export type ActionRequest = S["ActionRequestRequest"];
export type ComposeRequest = S["ComposeRequest"];
export type Queued = S["Queued"];
export type Draft = S["Draft"];
export type Uploaded = S["Uploaded"];
export type Template = S["Template"];
export type Note = S["Note"];
export type ContactSuggestion = S["ContactSuggestion"];
export type Assignee = S["Assignee"];
export type SendAs = S["SendAs"];
export type Vacation = S["Vacation"];
export type Filter = S["Filter"];
export type MailSettings = S["MailSettings"];
export type WorkspaceDomain = S["WorkspaceDomain"];

export type Stats = {
  range_days: number;
  generated_at: string;
  kpis: { unread: number; received_today: number; sent_today: number; avg_first_response_minutes: number | null; needs_reconnect: number };
  series: { date: string; received: number; sent: number }[];
  mailboxes: {
    id: number; email: string; name: string; office: string; colour: string; provider: Mailbox["provider"]; status: MailboxStatusName;
    unread: number; last_synced_at: string | null; last_activity_at: string | null; sync_progress: { done?: number; total?: number };
  }[];
  top_senders: { email: string; name: string; count: number }[];
  unanswered: { id: number; subject: string; mailbox_id: number; mailbox: string; colour: string; from: Address; waiting_hours: number }[];
};

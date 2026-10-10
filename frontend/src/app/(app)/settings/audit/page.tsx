"use client";

import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { controlClass, SelectField } from "@/components/ui/form";
import { ChevronDownIcon, DownloadIcon, ShieldIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { fullDate } from "@/lib/format";
import { errorMessage, query, request } from "@/services/api/client";
import type { AuditPage, User } from "@/services/api/types";
import { useMailboxSummaries } from "@/platforms/gmail/api/queries";
import { cn } from "@/utils/cn";

const ACTIONS = [
  { value: "", label: "All activity" },
  { value: "mail.open_thread", label: "Opened a conversation" },
  { value: "mail.send*", label: "Sent mail" },
  { value: "mail.*", label: "Any mail action" },
  { value: "mailbox.*", label: "Mailbox connections" },
  { value: "auth.*", label: "Sign-ins" },
  { value: "users.*", label: "User changes" },
  { value: "roles.*", label: "Role changes" },
  { value: "settings.*", label: "Settings changes" },
  { value: "audit.export", label: "Audit exports" },
];

/** "mail.open_thread" → "Mail · open thread" */
const actionLabel = (action: string) => {
  const [area, ...rest] = action.split(".");
  return `${area.charAt(0).toUpperCase()}${area.slice(1)} · ${rest.join(".").replace(/_/g, " ")}`;
};

export default function AuditPageView() {
  usePageTitle({ page: "Audit log", section: "Settings" });
  const { can } = useSession();
  const boxes = useMailboxSummaries();
  const users = useQuery({ queryKey: ["settings", "users"], queryFn: () => request<User[]>("settings/users/"), enabled: can("identity.manage_users"), staleTime: 60_000 });
  const [filters, setFilters] = useState({ actor: "", mailbox: "", action: "", from: "", to: "" });
  const [open, setOpen] = useState<number | null>(null);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch }));

  const events = useInfiniteQuery({
    queryKey: ["audit", filters],
    queryFn: ({ pageParam }) => request<AuditPage>(`audit/events/${query({ ...filters, cursor: pageParam })}`),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: can("audit.view_auditevent"),
    placeholderData: keepPreviousData,
  });
  const rows = events.data?.pages.flatMap((p) => p.results) ?? [];

  if (!can("audit.view_auditevent")) return <Page><PageHeader title="Audit log" description="Only administrators can see the audit log." /></Page>;

  return (
    <Page wide>
      <PageHeader title="Audit log" description="Every sign-in, mailbox connection, opened conversation, sent message and settings change. Entries cannot be edited."
        actions={<a href={`/api/v1/audit/events/export/${query(filters)}`} className="inline-flex h-10 items-center gap-2 rounded-lg border border-card-border bg-card-surface-area px-4 text-sm font-medium text-text-primary hover:border-primary-500 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"><DownloadIcon size={16} />Export CSV</a>} />

      <div className="mb-4 grid gap-3 rounded-xl border border-card-border bg-card-surface-area p-3 sm:grid-cols-2 lg:grid-cols-5">
        <SelectField label="Activity" value={filters.action} onChange={(e) => set({ action: e.target.value })} options={ACTIONS} />
        <SelectField label="Mailbox" value={filters.mailbox} onChange={(e) => set({ mailbox: e.target.value })} options={[{ value: "", label: "All mailboxes" }, ...boxes.map((b) => ({ value: String(b.id), label: b.email }))]} />
        {users.data ? <SelectField label="Person" value={filters.actor} onChange={(e) => set({ actor: e.target.value })} options={[{ value: "", label: "Everyone" }, ...users.data.map((u) => ({ value: String(u.id), label: u.display_name }))]} /> : <div className="hidden lg:block" />}
        <label className="flex flex-col gap-2 text-sm"><span className="font-medium">From</span><input type="date" value={filters.from} onChange={(e) => set({ from: e.target.value })} className={controlClass} /></label>
        <label className="flex flex-col gap-2 text-sm"><span className="font-medium">To</span><input type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => set({ to: e.target.value })} className={controlClass} /></label>
      </div>

      {events.isPending || (events.error && !events.data) ? <RequestState variant="table" loading={events.isPending} error={errorMessage(events.error)} onRetry={() => events.refetch()} /> : rows.length === 0 ? (
        <div className="rounded-xl border border-card-border bg-card-surface-area"><EmptyState icon={<ShieldIcon />} title="No matching activity" body="Try a wider date range or another filter." /></div>
      ) : (
        <div className={cn("overflow-x-auto rounded-xl border border-card-border bg-card-surface-area", events.isPlaceholderData && "opacity-70")}>
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-card-border bg-background-gray-secondary_alt/40 text-left text-xs text-text-tertiary">
              <tr><th className="px-4 py-2.5 font-medium">Time</th><th className="px-4 py-2.5 font-medium">Person</th><th className="px-4 py-2.5 font-medium">Activity</th><th className="px-4 py-2.5 font-medium">Mailbox</th><th className="px-4 py-2.5 font-medium">IP</th><th className="w-10" /></tr>
            </thead>
            <tbody className="divide-y divide-card-border">
              {rows.map((event) => (
                <Fragment key={event.id}>
                  <tr className="hover:bg-background-gray-secondary_alt/30">
                    <td className="px-4 py-2.5 whitespace-nowrap text-text-secondary">{fullDate(event.created_at)}</td>
                    <td className="px-4 py-2.5 text-text-primary">{event.actor_email || "System"}</td>
                    <td className="px-4 py-2.5"><span className="font-medium text-text-primary">{actionLabel(event.action)}</span>{event.target_type && <span className="ml-1.5 text-xs text-text-tertiary">{event.target_type} {event.target_id}</span>}</td>
                    <td className="px-4 py-2.5 text-text-secondary">{event.mailbox_email || "—"}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-text-tertiary">{event.ip || "—"}</td>
                    <td className="px-2 text-right">
                      <Button size="sm" appearance="ghost" iconOnly aria-label="Details" aria-expanded={open === event.id} onPress={() => setOpen(open === event.id ? null : event.id)}>
                        <ChevronDownIcon className={cn("transition-transform", open === event.id && "rotate-180")} />
                      </Button>
                    </td>
                  </tr>
                  {open === event.id && (
                    <tr className="bg-background-gray-secondary_alt/30">
                      <td colSpan={6} className="px-4 py-3 text-xs">
                        <p className="mb-1 text-text-tertiary">Browser: {event.user_agent || "—"}</p>
                        <pre className="max-h-48 overflow-auto rounded-lg bg-card-surface-area p-3 font-mono whitespace-pre-wrap text-text-secondary">{JSON.stringify(event.metadata ?? {}, null, 2)}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {events.hasNextPage && (
            <div className="flex justify-center border-t border-card-border p-3"><Button appearance="outline" onPress={() => events.fetchNextPage()} isPending={events.isFetchingNextPage}>Load more</Button></div>
          )}
        </div>
      )}
    </Page>
  );
}

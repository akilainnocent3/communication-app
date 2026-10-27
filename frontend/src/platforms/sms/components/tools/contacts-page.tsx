"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { BlockIcon, SearchIcon, UsersIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { m } from "@/i18n";
import { dateTime } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { ContactRow } from "@/services/api/types";
import { useContacts, useDeviceScope, useDeviceSummaries } from "../../api/queries";

/** Contacts seen on each phone (only numbers that appear in conversations) and blocked numbers. */
export function ContactsPage({ blocked = false }: { blocked?: boolean }) {
  usePageTitle({ page: blocked ? "Blocked numbers" : "Contacts", section: "Contacts" });
  const [scope] = useDeviceScope();
  const [q, setQ] = useState("");
  const contacts = useContacts(scope, q.trim(), blocked ? true : undefined);
  const rows = contacts.data?.pages.flatMap((page) => page.results) ?? [];
  return (
    <Page wide key={scope}>
      <PageHeader title={blocked ? "Blocked numbers" : "Contacts"} description={blocked
        ? "Numbers blocked on the phones. Blocking here blocks the number on the phone too (Android's blocked numbers list)."
        : "People and senders that appear in the phones' conversations, with names from the phone's address book. The rest of the address book is never copied."} />
      <label className="relative mb-4 block max-w-sm">
        <span className="sr-only">{m.sms.search}</span>
        <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-icon-tertiary" />
        <input value={q} onChange={(event) => setQ(event.target.value)} placeholder={m.sms.search} type="search"
          className="h-10 w-full rounded-lg border border-card-border bg-input-background pr-3 pl-9 text-sm text-text-primary outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20" />
      </label>
      {contacts.isPending || (contacts.error && !rows.length) ? <RequestState loading={contacts.isPending} error={errorMessage(contacts.error)} onRetry={() => contacts.refetch()} variant="table" /> : rows.length === 0 ? (
        <SectionCard><EmptyState icon={blocked ? <BlockIcon /> : <UsersIcon />} title={blocked ? "No blocked numbers" : "No contacts yet"} body={blocked ? "Block a number from a conversation's menu." : "Contacts appear as messages arrive."} /></SectionCard>
      ) : (
        <SectionCard padding="none" className="overflow-hidden" bodyClassName="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="border-b border-card-border bg-background-gray-secondary_alt/40 text-left text-xs text-text-tertiary">
              <tr><th className="px-4 py-2.5 font-medium">Contact</th><th className="px-4 py-2.5 font-medium">Phone</th><th className="px-4 py-2.5 text-right font-medium">Messages</th><th className="px-4 py-2.5 font-medium">Last contact</th><th className="px-4 py-2.5"><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody className="divide-y divide-card-border">{rows.map((row) => <Row key={row.id} row={row} />)}</tbody>
          </table>
          {contacts.hasNextPage && <div className="flex justify-center p-3"><Button size="sm" appearance="outline" onPress={() => contacts.fetchNextPage()} isPending={contacts.isFetchingNextPage}>Load more</Button></div>}
        </SectionCard>
      )}
    </Page>
  );
}

function Row({ row }: { row: ContactRow }) {
  const client = useQueryClient();
  const devices = useDeviceSummaries();
  const canManage = !!devices.find((device) => device.id === row.device.id)?.permissions.manage;
  const toggle = async () => {
    try {
      if (row.is_blocked) await mutate(`sms/blocked/${row.id}/`, "DELETE");
      else await mutate("sms/blocked/", "POST", { device: row.device.id, address: row.address });
      toast.success(row.is_blocked ? m.sms.done.unblock : m.sms.done.block);
      client.invalidateQueries({ queryKey: ["sms", "contacts"] });
    } catch (error) { toast.error(errorMessage(error)); }
  };
  return (
    <tr className="hover:bg-background-gray-secondary_alt/30">
      <td className="px-4 py-3"><p className="font-medium text-text-primary">{row.name || row.display}</p>{row.name && <p className="text-xs text-text-tertiary">{row.display}</p>}</td>
      <td className="px-4 py-3 text-text-secondary"><span style={{ color: row.device.colour }}>●</span> {row.device.name}</td>
      <td className="px-4 py-3 text-right tabular-nums">{row.messages}</td>
      <td className="px-4 py-3 text-text-secondary">{row.last_contact_at ? dateTime(row.last_contact_at) : "—"}</td>
      <td className="px-4 py-3 text-right whitespace-nowrap">
        {row.conversation && <Link href={`/sms/inbox?c=${row.conversation}`} className="mr-3 text-sm font-medium text-primary-500 hover:underline">Open</Link>}
        {canManage && row.kind !== "alphanumeric" && <Button size="sm" appearance="ghost" onPress={toggle}>{row.is_blocked ? m.sms.actions.unblock : m.sms.actions.block}</Button>}
      </td>
    </tr>
  );
}

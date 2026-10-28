"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { CallbackIcon, MessageIcon, PhoneIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard, StatCard } from "@/components/ui/section-card";
import { m } from "@/i18n";
import { dateTime } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import type { CustomerDetail } from "@/services/api/types";
import { useSaveCustomer } from "@/platforms/calls/api/actions";
import { useCustomer, useCustomerTimeline } from "@/platforms/calls/api/queries";
import { CallbackDialog, type CallbackSeed } from "@/platforms/calls/components/callback-dialog";
import { duration, resultLabel } from "@/platforms/calls/lib/labels";

const FIELD = "h-10 w-full rounded-lg border border-card-border bg-card-surface-area px-3 text-sm text-text-primary disabled:opacity-60";

export default function CustomerPage() {
  const { id } = useParams<{ id: string }>();
  const customer = useCustomer(Number(id));
  const timeline = useCustomerTimeline(Number(id));
  const [seed, setSeed] = useState<CallbackSeed | null>(null);
  usePageTitle({ page: "Directory", detail: customer.data?.display_name || customer.data?.display_number, section: "Calls" });
  if (customer.isPending) return <Page><PageSkeleton /></Page>;
  if (customer.error) return <Page><RequestState loading={false} error={errorMessage(customer.error)} onRetry={() => customer.refetch()} /></Page>;
  const data = customer.data!;
  return (
    <Page wide>
      <PageHeader eyebrow="Customer" title={data.display_name || data.display_number} description={data.display_name ? data.display_number : "No name in the directory yet."}
        actions={<Button onPress={() => setSeed({ number: data.key, customer: data.id, title: data.display_name || data.display_number })}><CallbackIcon size={16} />{m.calls.createCallback}</Button>} />
      <dl className="mb-5 grid grid-cols-3 gap-2 sm:gap-3 md:max-w-xl">
        <StatCard label="Calls" value={data.stats.calls as number} />
        <StatCard label="Missed" value={data.stats.missed as number} tone={(data.stats.missed as number) ? "error" : undefined} />
        <StatCard label="Unreturned" value={data.stats.unreturned as number} tone={(data.stats.unreturned as number) ? "warning" : undefined} />
      </dl>
      <div className="grid gap-4 sm:gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Details key={data.id} customer={data} />
        <SectionCard title="Timeline" description="Calls and messages on the phones you can open">
          {timeline.isPending ? <RequestState loading onRetry={() => timeline.refetch()} /> : (timeline.data ?? []).length === 0 ? <p className="text-sm text-text-tertiary">Nothing yet.</p> : (
            <ol className="divide-y divide-card-border" data-customer-timeline="">
              {timeline.data!.map((item) => (
                <li key={`${item.kind}-${item.call_id ?? item.conversation_id}-${item.at}`} className="flex items-start gap-2.5 py-2 text-sm">
                  {item.kind === "call" ? <PhoneIcon size={16} className="mt-0.5 text-icon-tertiary" /> : <MessageIcon size={16} className="mt-0.5 text-icon-tertiary" />}
                  <div className="min-w-0 flex-1">
                    {item.kind === "call"
                      ? <Link href={`/calls/log/all?call=${item.call_id}`} className="text-text-primary hover:underline">{m.calls.direction[item.direction as "in" | "out"]} call · {resultLabel(item.result)}{item.talk_seconds ? ` · ${duration(item.talk_seconds)}` : ""}</Link>
                      : <Link href={`/sms/inbox?c=${item.conversation_id}`} className="block truncate text-text-primary hover:underline">{item.direction === "in" ? "Received" : "Sent"}: {item.snippet || "(hidden)"}</Link>}
                    <p className="text-xs text-text-tertiary">{item.device} · {dateTime(item.at)}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </SectionCard>
      </div>
      <CallbackDialog key={seed ? JSON.stringify(seed) : "none"} seed={seed} onClose={() => setSeed(null)} />
    </Page>
  );
}

function Details({ customer }: { customer: CustomerDetail }) {
  const save = useSaveCustomer(customer.id);
  const [name, setName] = useState(customer.display_name);
  const [organisation, setOrganisation] = useState(customer.organisation);
  const [tags, setTags] = useState(customer.tags.join(", "));
  const [notes, setNotes] = useState(customer.notes);
  const [optOut, setOptOut] = useState(customer.auto_sms_opt_out);
  const disabled = !customer.can_edit;
  return (
    <SectionCard title="Details" description={customer.can_edit ? "Notes are encrypted and never sent to phones." : "You can view this customer but not edit it."}>
      <form className="grid gap-3" onSubmit={(e) => {
        e.preventDefault();
        save.mutate({ display_name: name, organisation, tags: tags.split(",").map((t) => t.trim()).filter(Boolean), notes, auto_sms_opt_out: optOut });
      }}>
        <label className="grid gap-1 text-sm"><span className="font-medium">Name</span><input disabled={disabled} value={name} onChange={(e) => setName(e.target.value)} className={FIELD} /></label>
        <label className="grid gap-1 text-sm"><span className="font-medium">Organisation</span><input disabled={disabled} value={organisation} onChange={(e) => setOrganisation(e.target.value)} className={FIELD} /></label>
        <label className="grid gap-1 text-sm"><span className="font-medium">Tags</span><input disabled={disabled} value={tags} onChange={(e) => setTags(e.target.value)} placeholder="vip, wholesale" className={FIELD} /></label>
        <label className="grid gap-1 text-sm"><span className="font-medium">Notes</span>
          <textarea disabled={disabled} rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full rounded-lg border border-card-border bg-card-surface-area px-3 py-2 text-sm disabled:opacity-60" />
        </label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={disabled} checked={optOut} onChange={(e) => setOptOut(e.target.checked)} />Never send the automatic missed-call SMS</label>
        {customer.aliases.length > 0 && <p className="text-xs text-text-tertiary">Also: {customer.aliases.join(", ")}</p>}
        <dl className="grid grid-cols-2 gap-2 text-xs text-text-tertiary">
          <div><dt>First call</dt><dd className="text-text-primary">{customer.first_seen_call ? dateTime(customer.first_seen_call) : "—"}</dd></div>
          <div><dt>First message</dt><dd className="text-text-primary">{customer.first_seen_sms ? dateTime(customer.first_seen_sms) : "—"}</dd></div>
        </dl>
        {customer.can_edit && <div><Button type="submit" isPending={save.isPending}>{m.common.save}</Button></div>}
      </form>
    </SectionCard>
  );
}

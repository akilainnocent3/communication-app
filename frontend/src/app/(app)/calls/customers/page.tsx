"use client";

import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogBody, DialogFooter, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { PlusIcon, SearchIcon, UsersIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { Chip } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import { ago } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import { useMergeCustomers, useSaveCustomer } from "@/platforms/calls/api/actions";
import { useCustomers } from "@/platforms/calls/api/queries";

const FIELD = "h-10 w-full rounded-lg border border-card-border bg-card-surface-area px-3 text-sm text-text-primary";

export default function CustomersPage() {
  usePageTitle({ page: "Directory", section: "Calls" });
  const { can } = useSession();
  const [q, setQ] = useState("");
  const search = useDeferredValue(q);
  const list = useCustomers(search.trim());
  const rows = useMemo(() => list.data?.pages.flatMap((page) => page.results) ?? [], [list.data]);
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const merge = useMergeCustomers();
  const manager = can("directory.manage_customers");

  return (
    <Page wide>
      <PageHeader eyebrow="Customers" title="Directory" description="One entry per number, shared by SMS and Calls. Names here show as caller ID on the phones that know the customer."
        actions={manager ? <Button onPress={() => setAdding(true)}><PlusIcon size={16} />Add customer</Button> : undefined} />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="relative min-w-56 flex-1 sm:max-w-sm">
          <span className="sr-only">Search customers</span>
          <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-icon-tertiary" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, organisation or number" className="h-9 w-full rounded-lg border border-card-border bg-card-surface-area pr-2 pl-8 text-sm" />
        </label>
        {manager && selected.length >= 2 && (
          <Button size="sm" appearance="outline" onPress={() => merge.mutateAsync({ target: selected[0], sources: selected.slice(1) }).then(() => setSelected([]))}>
            Merge {selected.length} into the first
          </Button>
        )}
      </div>
      {list.isPending ? <RequestState loading variant="table" onRetry={() => list.refetch()} /> : list.error && !rows.length ? (
        <RequestState loading={false} error={errorMessage(list.error)} onRetry={() => list.refetch()} />
      ) : rows.length === 0 ? (
        <SectionCard><EmptyState icon={<UsersIcon />} title={m.calls.empty.customers.title} body={m.calls.empty.customers.body} /></SectionCard>
      ) : (
        <SectionCard padding="none">
          <ul className="divide-y divide-card-border" data-customers="">
            {rows.map((customer) => (
              <li key={customer.id} className="flex items-center gap-3 px-4 py-2.5">
                {manager && <input type="checkbox" aria-label={`Select ${customer.display_name || customer.display_number}`} checked={selected.includes(customer.id)}
                  onChange={() => setSelected((s) => (s.includes(customer.id) ? s.filter((x) => x !== customer.id) : [...s, customer.id]))} />}
                <Link href={`/calls/customers/${customer.id}`} className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-text-primary">{customer.display_name || customer.display_number}</span>
                  <span className="block truncate text-xs text-text-tertiary">{[customer.display_name ? customer.display_number : "", customer.organisation, customer.owner && `Owner ${customer.owner}`].filter(Boolean).join(" · ")}</span>
                </Link>
                <span className="hidden gap-1 sm:flex">{customer.tags.slice(0, 3).map((tag) => <Chip key={tag}>{tag}</Chip>)}</span>
                <span className="shrink-0 text-xs text-text-tertiary">{customer.last_seen_call ? `Called ${ago(customer.last_seen_call)}` : customer.last_seen_sms ? `Texted ${ago(customer.last_seen_sms)}` : "—"}</span>
              </li>
            ))}
          </ul>
          {list.hasNextPage && <div className="border-t border-card-border p-3 text-center"><Button appearance="outline" size="sm" onPress={() => list.fetchNextPage()}>Load more</Button></div>}
        </SectionCard>
      )}
      <AddCustomer open={adding} onClose={() => setAdding(false)} />
    </Page>
  );
}

function AddCustomer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const save = useSaveCustomer();
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [organisation, setOrganisation] = useState("");
  return (
    <Dialog isOpen={open} onOpenChange={(isOpen) => !isOpen && onClose()} className="max-w-md" aria-label="Add customer">
      <DialogHeader><DialogTitle>Add customer</DialogTitle></DialogHeader>
      <DialogBody>
        <form id="customer-form" className="grid gap-3" onSubmit={(e) => { e.preventDefault(); save.mutate({ number, display_name: name, organisation }, { onSuccess: onClose }); }}>
          <label className="grid gap-1 text-sm"><span className="font-medium">Number, short code or sender name</span><input required value={number} onChange={(e) => setNumber(e.target.value)} className={FIELD} /></label>
          <label className="grid gap-1 text-sm"><span className="font-medium">Name</span><input value={name} onChange={(e) => setName(e.target.value)} className={FIELD} /></label>
          <label className="grid gap-1 text-sm"><span className="font-medium">Organisation</span><input value={organisation} onChange={(e) => setOrganisation(e.target.value)} className={FIELD} /></label>
        </form>
      </DialogBody>
      <DialogFooter><Button appearance="outline" onPress={onClose}>{m.common.cancel}</Button><Button type="submit" form="customer-form" isPending={save.isPending}>{m.common.save}</Button></DialogFooter>
    </Dialog>
  );
}

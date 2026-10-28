"use client";

import { useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage } from "@/services/api/client";
import type { CallOutcome } from "@/services/api/types";
import { useCallsWrite } from "@/platforms/calls/api/actions";
import { callsKeys } from "@/platforms/calls/api/keys";
import { useOutcomes } from "@/platforms/calls/api/queries";

export default function OutcomesPage() {
  usePageTitle({ page: "Outcomes", section: "Calls" });
  const { can } = useSession();
  const manage = can("calls.manage_settings");
  const outcomes = useOutcomes();
  const write = useCallsWrite<CallOutcome>(callsKeys.outcomes());
  const [name, setName] = useState("");
  const [colour, setColour] = useState("#3758f9");
  return (
    <Page>
      <PageHeader eyebrow="Tools" title="Outcomes" description="Dispositions staff choose on the post-call card or the admin adds to a call. Used outcomes are retired, not deleted." />
      <SectionCard>
        {outcomes.isPending || outcomes.error ? <RequestState loading={outcomes.isPending} error={outcomes.error ? errorMessage(outcomes.error) : undefined} onRetry={() => outcomes.refetch()} /> : (
          <ul className="divide-y divide-card-border" data-outcomes="">
            {outcomes.data!.map((o) => (
              <li key={o.id} className="flex items-center gap-3 py-2.5 text-sm">
                <span aria-hidden="true" className="size-3 rounded-full" style={{ background: o.colour }} />
                <span className={o.is_active ? "flex-1 text-text-primary" : "flex-1 text-text-tertiary line-through"}>{o.name}</span>
                {manage && o.is_active && <Button size="xs" appearance="ghost" onPress={() => write.mutateAsync({ path: `calls/outcomes/${o.id}/`, method: "DELETE" })}>Retire</Button>}
                {manage && !o.is_active && <Button size="xs" appearance="ghost" onPress={() => write.mutateAsync({ path: `calls/outcomes/${o.id}/`, method: "PATCH", body: { is_active: true } })}>Restore</Button>}
              </li>
            ))}
          </ul>
        )}
        {manage && (
          <form className="mt-4 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); write.mutate({ path: "calls/outcomes/", method: "POST", body: { name, colour } }, { onSuccess: () => setName("") }); }}>
            <label className="grid gap-1 text-sm"><span className="font-medium">New outcome</span><input required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} className="h-9 rounded-lg border border-card-border bg-card-surface-area px-3 text-sm" /></label>
            <label className="grid gap-1 text-sm"><span className="font-medium">Colour</span><input type="color" value={colour} onChange={(e) => setColour(e.target.value)} className="h-9 w-14 rounded-lg border border-card-border bg-card-surface-area" /></label>
            <Button type="submit" isPending={write.isPending}>Add</Button>
          </form>
        )}
      </SectionCard>
    </Page>
  );
}

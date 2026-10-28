"use client";

import { useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage } from "@/services/api/client";
import type { CarrierTariff } from "@/services/api/types";
import { useCallsWrite } from "@/platforms/calls/api/actions";
import { callsKeys } from "@/platforms/calls/api/keys";
import { useTariffs } from "@/platforms/calls/api/queries";

const INPUT = "h-9 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary";

export default function TariffsPage() {
  usePageTitle({ page: "Tariffs", section: "Calls" });
  const { can } = useSession();
  const manage = can("calls.manage_settings");
  const tariffs = useTariffs();
  const write = useCallsWrite<CarrierTariff>(callsKeys.tariffs());
  const [carrier, setCarrier] = useState("");
  const [price, setPrice] = useState("");
  const [increment, setIncrement] = useState("60");
  return (
    <Page>
      <PageHeader eyebrow="Tools" title="Tariffs" description="Price per outgoing minute by carrier (as the SIM names it), for the dashboard's cost estimate." />
      <SectionCard>
        {tariffs.isPending || tariffs.error ? <RequestState loading={tariffs.isPending} error={tariffs.error ? errorMessage(tariffs.error) : undefined} onRetry={() => tariffs.refetch()} /> : (
          tariffs.data!.length === 0 ? <p className="text-sm text-text-tertiary">No tariffs yet.</p> : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-text-tertiary"><tr><th className="py-1.5 font-medium">Carrier</th><th className="py-1.5 text-right font-medium">Per minute</th><th className="py-1.5 text-right font-medium">Billing step</th><th /></tr></thead>
              <tbody className="divide-y divide-card-border">
                {tariffs.data!.map((t) => (
                  <tr key={t.id}><td className="py-2">{t.carrier}</td><td className="py-2 text-right tabular-nums">{t.currency} {t.per_minute}</td><td className="py-2 text-right tabular-nums">{t.billing_increment_seconds}s</td>
                    <td className="py-2 text-right">{manage && <Button size="xs" appearance="ghost" onPress={() => write.mutateAsync({ path: `calls/tariffs/${t.id}/`, method: "DELETE" })}>Delete</Button>}</td></tr>
                ))}
              </tbody>
            </table>
          )
        )}
        {manage && (
          <form className="mt-4 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); write.mutate({ path: "calls/tariffs/", method: "POST", body: { carrier, per_minute: price, billing_increment_seconds: Number(increment) } }, { onSuccess: () => { setCarrier(""); setPrice(""); } }); }}>
            <label className="grid gap-1 text-sm"><span className="font-medium">Carrier</span><input required value={carrier} onChange={(e) => setCarrier(e.target.value)} placeholder="Vodacom" className={INPUT} /></label>
            <label className="grid gap-1 text-sm"><span className="font-medium">TZS per minute</span><input required inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="35.00" className={INPUT} /></label>
            <label className="grid gap-1 text-sm"><span className="font-medium">Billing step (s)</span><select value={increment} onChange={(e) => setIncrement(e.target.value)} className={INPUT}><option value="60">60</option><option value="30">30</option><option value="1">1</option></select></label>
            <Button type="submit" isPending={write.isPending}>Add</Button>
          </form>
        )}
      </SectionCard>
    </Page>
  );
}

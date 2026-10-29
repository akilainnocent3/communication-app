"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { useSession } from "@/components/shell/session-provider";
import { Field } from "@/components/ui/field";
import { SelectField } from "@/components/ui/form";
import { m } from "@/i18n";
import { errorMessage, fieldError, mutate, request } from "@/services/api/client";
import type { CallEnrollmentCreateRequest, EnrollmentCreated, Office, User } from "@/services/api/types";
import { EnrollmentCode } from "@/platforms/shared/enrollment-code";
import { useCallDevices } from "../api/queries";
import { callsKeys } from "../api/keys";

/**
 * "Enroll OCM Phone": a code for the separate dialer app (ocmphone://enroll?server=…&token=…, decision 80). The admin
 * may link it to the SMS phone on the same handset, so the missed-call SMS goes out through OCM Messages there.
 */
export function CallsEnrollDialog({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const client = useQueryClient();
  const { can } = useSession();
  const offices = useQuery({ queryKey: ["settings", "offices"], queryFn: () => request<Office[]>("settings/offices/"), enabled: isOpen, staleTime: 60_000 });
  const users = useQuery({ queryKey: ["settings", "users"], queryFn: () => request<User[]>("settings/users/"), enabled: isOpen && can("identity.manage_users"), staleTime: 60_000 });
  const smsPhones = useCallDevices(true, isOpen);
  const [form, setForm] = useState<CallEnrollmentCreateRequest>({ name: "", office: 0, assigned_to: null, backfill_days: 90, companion: null });
  const create = useMutation({ mutationFn: (body: CallEnrollmentCreateRequest) => mutate<EnrollmentCreated>("calls/enrollments/", "POST", body) });
  const invite = create.data;
  const officeId = form.office || offices.data?.[0]?.id || 0;

  const close = (open: boolean) => {
    if (!open) { create.reset(); setForm((f) => ({ ...f, name: "", companion: null })); }
    onOpenChange(open);
  };
  const pickCompanion = (id: string) => {
    const phone = (smsPhones.data ?? []).find((d) => d.id === id);
    const office = offices.data?.find((o) => o.name === phone?.office);
    setForm({ ...form, companion: id || null, name: form.name || phone?.name || "", office: office?.id ?? form.office });
  };

  return (
    <Dialog isOpen={isOpen} onOpenChange={close} className="max-w-xl" aria-label={m.calls.enroll.title}>
      <DialogHeader><DialogTitle>{m.calls.enroll.title}</DialogTitle></DialogHeader>
      {!invite ? (
        <form className="mt-4 space-y-4" onSubmit={(event) => { event.preventDefault(); create.mutate({ ...form, office: officeId }); }}>
          <p className="text-sm text-text-tertiary">{m.calls.enroll.intro}</p>
          <SelectField label={m.calls.enroll.companion} value={form.companion ?? ""} onChange={(e) => pickCompanion(e.target.value)} hint={m.calls.enroll.companionHint}
            options={[{ value: "", label: m.calls.enroll.none }, ...(smsPhones.data ?? []).map((d) => ({ value: d.id, label: `${d.name} · ${d.code}` }))]} error={fieldError(create.error, "companion")} />
          <Field label="Phone name" value={form.name} onChange={(name) => setForm({ ...form, name })} placeholder="e.g. Arusha front desk" isRequired error={fieldError(create.error, "name")} autoFocus />
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField label="Office" value={officeId} onChange={(e) => setForm({ ...form, office: Number(e.target.value) })} options={(offices.data ?? []).map((o) => ({ value: o.id, label: o.name }))} error={fieldError(create.error, "office")} />
            <SelectField label="Assigned staff (optional)" value={form.assigned_to ?? ""} onChange={(e) => setForm({ ...form, assigned_to: e.target.value ? Number(e.target.value) : null })}
              options={[{ value: "", label: "Nobody" }, ...(users.data ?? []).filter((u) => u.is_active !== false).map((u) => ({ value: u.id, label: u.display_name }))]} />
          </div>
          <SelectField label="Copy calls from the last" value={form.backfill_days ?? 90} onChange={(e) => setForm({ ...form, backfill_days: Number(e.target.value) })}
            options={[7, 30, 90, 180, 365].map((d) => ({ value: d, label: `${d} days` }))} hint="Older calls stay in the phone's call log only." />
          {create.error && !fieldError(create.error, "name") && !fieldError(create.error, "companion") && <p role="alert" className="text-sm text-error-500">{errorMessage(create.error)}</p>}
          <div className="flex justify-end gap-2">
            <Button appearance="outline" onPress={() => close(false)}>{m.common.cancel}</Button>
            <Button type="submit" isPending={create.isPending} isDisabled={!form.name.trim() || !officeId}>Create enrollment code</Button>
          </div>
        </form>
      ) : (
        <EnrollmentCode invite={invite} api="calls/enrollments" statusKey={callsKeys.enrollment(invite.id)}
          text={{ scan: m.calls.enroll.scan, waiting: m.calls.enroll.waiting, enrolled: m.calls.enroll.enrolled }}
          deviceHref={() => "/calls/devices"} onClose={() => close(false)}
          onEnrolled={() => client.invalidateQueries({ queryKey: ["calls", "devices"] })} />
      )}
    </Dialog>
  );
}

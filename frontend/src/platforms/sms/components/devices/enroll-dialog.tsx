"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { ME_KEY, useSession } from "@/components/shell/session-provider";
import { Field } from "@/components/ui/field";
import { SelectField, SwitchRow } from "@/components/ui/form";
import { m } from "@/i18n";
import { errorMessage, fieldError, mutate, request } from "@/services/api/client";
import type { EnrollmentCreated, EnrollmentCreateRequest, Office, User } from "@/services/api/types";
import { EnrollmentCode } from "@/platforms/shared/enrollment-code";
import { smsKeys } from "../../api/keys";

/**
 * "Enroll phone": an admin names the phone, picks its office and options, and gets a single-use 24 h code with a
 * server-side QR (cmsms://enroll?server=…&token=…) for the OCM Messages app. The status is polled every 3 s.
 */
export function EnrollDialog({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const client = useQueryClient();
  const { can } = useSession();
  const offices = useQuery({ queryKey: ["settings", "offices"], queryFn: () => request<Office[]>("settings/offices/"), enabled: isOpen, staleTime: 60_000 });
  const users = useQuery({ queryKey: ["settings", "users"], queryFn: () => request<User[]>("settings/users/"), enabled: isOpen && can("identity.manage_users"), staleTime: 60_000 });
  const [form, setForm] = useState<EnrollmentCreateRequest>({ name: "", office: 0, assigned_to: null, backfill_days: 90, signature_enabled: false, signature: "- Head Office", mark_read_on_open: true });
  const create = useMutation({
    mutationFn: (body: EnrollmentCreateRequest) => mutate<EnrollmentCreated>("sms/enrollments/", "POST", body),
    onSuccess: () => client.invalidateQueries({ queryKey: smsKeys.enrollments() }),
  });
  const invite = create.data;
  const officeId = form.office || offices.data?.[0]?.id || 0;

  const close = (open: boolean) => {
    if (!open) { create.reset(); setForm((f) => ({ ...f, name: "" })); }
    onOpenChange(open);
  };

  return (
    <Dialog isOpen={isOpen} onOpenChange={close} className="max-w-xl" aria-label={m.sms.devices.enrollTitle}>
      <DialogHeader><DialogTitle>{m.sms.devices.enrollTitle}</DialogTitle></DialogHeader>
      {!invite ? (
        <form className="mt-4 space-y-4" onSubmit={(event) => { event.preventDefault(); create.mutate({ ...form, office: officeId }); }}>
          <Field label="Phone name" value={form.name} onChange={(name) => setForm({ ...form, name })} placeholder="e.g. Arusha front desk" isRequired error={fieldError(create.error, "name")} autoFocus />
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField label="Office" value={officeId} onChange={(e) => setForm({ ...form, office: Number(e.target.value) })} options={(offices.data ?? []).map((o) => ({ value: o.id, label: o.name }))} error={fieldError(create.error, "office")} />
            <SelectField label="Assigned staff (optional)" value={form.assigned_to ?? ""} onChange={(e) => setForm({ ...form, assigned_to: e.target.value ? Number(e.target.value) : null })}
              options={[{ value: "", label: "Nobody" }, ...(users.data ?? []).filter((u) => u.is_active !== false).map((u) => ({ value: u.id, label: u.display_name }))]} />
          </div>
          <SelectField label="Copy messages from the last" value={form.backfill_days ?? 90} onChange={(e) => setForm({ ...form, backfill_days: Number(e.target.value) })}
            options={[7, 30, 90, 180, 365].map((d) => ({ value: d, label: `${d} days` }))} hint="Older messages stay on the phone only." />
          <div className="divide-y divide-card-border rounded-xl border border-card-border px-4">
            <SwitchRow title="Mark read on the phone when opened here" description="Opening a conversation in the admin marks it read on the phone too." checked={!!form.mark_read_on_open} onChange={(v) => setForm({ ...form, mark_read_on_open: v })} />
            <SwitchRow title="Add an admin signature" description="Appended to messages sent from the admin. Customers see it; it counts towards the SMS length." checked={!!form.signature_enabled} onChange={(v) => setForm({ ...form, signature_enabled: v })} />
            {form.signature_enabled && <div className="py-3"><Field label="Signature" value={form.signature ?? ""} onChange={(signature) => setForm({ ...form, signature })} maxLength={40} hint="Use a plain hyphen: dashes like “—” switch the whole SMS to Unicode (70 characters per SMS)." /></div>}
          </div>
          {create.error && !fieldError(create.error, "name") && <p role="alert" className="text-sm text-error-500">{errorMessage(create.error)}</p>}
          <div className="flex justify-end gap-2">
            <Button appearance="outline" onPress={() => close(false)}>{m.common.cancel}</Button>
            <Button type="submit" isPending={create.isPending} isDisabled={!form.name.trim() || !officeId}>Create enrollment code</Button>
          </div>
        </form>
      ) : (
        <EnrollmentCode invite={invite} api="sms/enrollments" statusKey={smsKeys.enrollment(invite.id)}
          text={{ scan: m.sms.devices.scan, waiting: m.sms.devices.waiting, enrolled: m.sms.devices.enrolled }}
          deviceHref={(id) => `/sms/devices/${id}`} onClose={() => close(false)}
          onEnrolled={() => { client.invalidateQueries({ queryKey: smsKeys.devices() }); client.invalidateQueries({ queryKey: ME_KEY }); }} />
      )}
    </Dialog>
  );
}

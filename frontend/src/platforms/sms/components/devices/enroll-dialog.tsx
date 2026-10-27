"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { ME_KEY, useSession } from "@/components/shell/session-provider";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { Field } from "@/components/ui/field";
import { SelectField, SwitchRow } from "@/components/ui/form";
import { CheckCircleIcon, CopyIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { dateTime } from "@/lib/format";
import { errorMessage, fieldError, mutate, request } from "@/services/api/client";
import type { Enrollment, EnrollmentCreated, EnrollmentCreateRequest, Office, User } from "@/services/api/types";
import { smsKeys } from "../../api/keys";

/**
 * "Enroll phone": an admin names the phone, picks its office and options, and gets a single-use 24 h code with a
 * server-side QR (cmsms://enroll?server=…&token=…). The status is polled every 3 s while the dialog is open.
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
  const status = useQuery({
    queryKey: smsKeys.enrollment(invite?.id ?? 0),
    queryFn: () => request<Enrollment>(`sms/enrollments/${invite!.id}/`),
    enabled: isOpen && !!invite,
    refetchInterval: (q) => (q.state.data?.state === "used" ? false : 3000),
  });
  const enrolled = status.data?.state === "used" ? status.data : null;
  const enrolledId = enrolled?.id;
  useEffect(() => {
    if (!enrolledId) return;
    client.invalidateQueries({ queryKey: smsKeys.devices() });
    client.invalidateQueries({ queryKey: ME_KEY });
  }, [enrolledId, client]);
  const officeId = form.office || offices.data?.[0]?.id || 0;

  const close = (open: boolean) => {
    if (!open) { create.reset(); setForm((f) => ({ ...f, name: "" })); }
    onOpenChange(open);
  };
  const copy = async () => {
    if (!invite) return;
    try { await navigator.clipboard.writeText(invite.code); toast.success("Code copied."); } catch { toast.error("Couldn't copy automatically. Select the code and copy it."); }
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
        <div className="mt-4 space-y-5 animate-fade-up" data-enroll-invite="">
          <p className="text-sm text-text-tertiary">{m.sms.devices.scan}</p>
          <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
            <div className="shrink-0 rounded-xl border border-card-border bg-white p-2.5 [&_svg]:size-40" aria-label="QR code for enrolling the phone" role="img"
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(invite.qr_svg, { USE_PROFILES: { svg: true } }) }} />
            <div className="w-full min-w-0 space-y-3">
              <label className="block text-xs font-medium text-text-secondary" htmlFor="enroll-code">Enrollment code</label>
              <div className="flex gap-2">
                <input id="enroll-code" readOnly value={invite.code} onFocus={(event) => event.currentTarget.select()}
                  className="h-10 min-w-0 flex-1 rounded-lg border border-card-border bg-background-gray-secondary_alt/50 px-3 font-mono text-xs text-text-primary focus:border-primary-500 focus:outline-none" />
                <Button appearance="outline" onPress={copy} aria-label="Copy code"><CopyIcon size={16} />{m.common.copy}</Button>
              </div>
              <p className="text-xs text-text-tertiary">Works once · expires {dateTime(invite.expires_at)} · {invite.name} · {invite.office.name}</p>
              <p className="text-xs text-text-tertiary">The phone holder sees the company monitoring notice and must accept it before the phone is enrolled.</p>
            </div>
          </div>
          <div role="status" aria-live="polite" className={enrolled ? "flex items-center gap-3 rounded-xl border border-success-500/40 bg-success-500/10 px-4 py-3" : "flex items-center gap-3 rounded-xl border border-card-border bg-background-gray-secondary_alt/40 px-4 py-3"}>
            {enrolled ? <CheckCircleIcon className="text-success-500" /> : <ActivityIndicator size="sm" decorative />}
            <span className="text-sm font-medium text-text-primary">{enrolled ? m.sms.devices.enrolled(enrolled.device?.code ?? "") : m.sms.devices.waiting}</span>
            {enrolled?.device && <Link href={`/sms/devices/${enrolled.device.id}`} onClick={() => close(false)} className="ml-auto text-sm font-medium text-primary-500 hover:underline">Open phone</Link>}
          </div>
          {status.data && status.data.failed_attempts > 0 && !enrolled && (
            <p className="text-xs text-warning-700 dark:text-warning-300">{status.data.failed_attempts} failed attempt{status.data.failed_attempts > 1 ? "s" : ""} ({status.data.last_failure}). After 5 the code stops working.</p>
          )}
          <div className="flex justify-end gap-2">
            {!enrolled && <Button appearance="ghost" onPress={async () => { try { await mutate(`sms/enrollments/${invite.id}/revoke/`, "POST"); toast("Code revoked."); close(false); } catch (e) { toast.error(errorMessage(e)); } }}>Revoke code</Button>}
            <Button appearance={enrolled ? "fill" : "outline"} onPress={() => close(false)}>{enrolled ? m.common.done : m.common.close}</Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

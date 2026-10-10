"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fromZonedTime, formatInTimeZone } from "date-fns-tz";
import { useState } from "react";
import { toast } from "sonner";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { controlClass, SwitchRow } from "@/components/ui/form";
import { VacationIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { timezone } from "@/lib/format";
import { errorMessage, fieldError, mutate, request } from "@/services/api/client";
import type { Vacation } from "@/services/api/types";
import { mailKeys } from "@/platforms/gmail/api/keys";
import { useMailboxes } from "@/platforms/gmail/api/queries";
import { RichTextField } from "@/platforms/gmail/compose/rich-text-field";
import { useToolMailbox } from "@/platforms/gmail/components/tool-mailbox";

const toDay = (iso?: string | null) => (iso ? formatInTimeZone(new Date(iso), timezone(), "yyyy-MM-dd") : "");
/** First day starts at 00:00 and the last day ends at 23:59:59 in the user's timezone. */
const fromDay = (day: string, end = false) => (day ? fromZonedTime(`${day}T${end ? "23:59:59" : "00:00:00"}`, timezone()).toISOString() : null);

export default function VacationPage() {
  usePageTitle({ page: "Vacation responder", section: "Tools" });
  const { mailbox, picker, empty } = useToolMailbox();
  const mailboxes = useMailboxes();
  const caps = mailboxes.data?.find((box) => box.id === mailbox?.id)?.capabilities;
  const vacation = useQuery({ queryKey: mailKeys.vacation(mailbox?.id ?? 0), queryFn: () => request<Vacation>(`mail/settings/${mailbox!.id}/vacation/`), enabled: !!mailbox && caps?.vacation !== false });

  return (
    <Page className="max-w-3xl">
      <PageHeader title="Vacation responder" description="Send an automatic reply while the office is closed or away." actions={picker} />
      {!mailbox ? empty : caps && !caps.vacation ? (
        <SectionCard><EmptyState icon={<VacationIcon />} title="Not available for this mailbox" body="Automatic replies for this mail server are set in its own webmail." /></SectionCard>
      ) : vacation.isPending ? <PageSkeleton /> : vacation.error ? (
        <RequestState loading={false} error={errorMessage(vacation.error)} onRetry={() => vacation.refetch()} />
      ) : <VacationForm key={mailbox.id} mailboxId={mailbox.id} initial={vacation.data!} />}
    </Page>
  );
}

function VacationForm({ mailboxId, initial }: { mailboxId: number; initial: Vacation }) {
  const client = useQueryClient();
  const [enabled, setEnabled] = useState(initial.enable_auto_reply);
  const [start, setStart] = useState(toDay(initial.start_time));
  const [end, setEnd] = useState(toDay(initial.end_time));
  const [subject, setSubject] = useState(initial.response_subject ?? "");
  const [body, setBody] = useState(initial.response_body_html ?? "");
  const [contacts, setContacts] = useState(!!initial.restrict_to_contacts);
  const [domain, setDomain] = useState(!!initial.restrict_to_domain);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const toggle = (on: boolean) => {
    setEnabled(on);
    if (on && !start) setStart(formatInTimeZone(new Date(), timezone(), "yyyy-MM-dd"));
  };

  const save = async () => {
    setBusy(true); setError(null);
    try {
      const data = await mutate<Vacation>(`mail/settings/${mailboxId}/vacation/`, "PUT", {
        enable_auto_reply: enabled, response_subject: subject, response_body_html: body, restrict_to_contacts: contacts, restrict_to_domain: domain,
        start_time: fromDay(start), end_time: fromDay(end, true),
      });
      client.setQueryData(mailKeys.vacation(mailboxId), data);
      toast.success(enabled ? "Vacation responder is on." : "Vacation responder is off.");
    } catch (e) { setError(e); } finally { setBusy(false); }
  };

  return (
    <SectionCard footer={<div className="flex justify-end"><Button onPress={save} isPending={busy}>Save changes</Button></div>}>
      <SwitchRow title="Vacation responder" description="Reply automatically to people who write to this mailbox (once every 4 days per sender)." checked={enabled} onChange={toggle} />
      <fieldset disabled={!enabled} className="mt-2 space-y-4 border-t border-card-border pt-4 disabled:opacity-60">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm"><span className="font-medium">First day</span><input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={controlClass} /></label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">Last day <span className="font-normal text-text-tertiary">(optional)</span></span>
            <input type="date" value={end} min={start || undefined} onChange={(e) => setEnd(e.target.value)} className={controlClass} aria-invalid={!!fieldError(error, "end_time") || undefined} />
            {fieldError(error, "end_time") && <span className="text-xs text-error-500">{fieldError(error, "end_time")}</span>}
          </label>
        </div>
        <Field label="Subject" value={subject} onChange={setSubject} placeholder="Office closed until Monday" isDisabled={!enabled} />
        <RichTextField label="Message" initial={initial.response_body_html ?? ""} onChange={setBody} placeholder="Thank you for your message. Our office is closed…" />
        <div className="divide-y divide-card-border">
          <SwitchRow title="Only reply to people in my contacts" checked={contacts} onChange={setContacts} disabled={!enabled} />
          <SwitchRow title="Only reply to people in my organisation" checked={domain} onChange={setDomain} disabled={!enabled} />
        </div>
      </fieldset>
      {!!error && !fieldError(error, "end_time") && <p role="alert" className="mt-3 text-sm text-error-500">{errorMessage(error)}</p>}
    </SectionCard>
  );
}

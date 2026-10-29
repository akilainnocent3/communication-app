"use client";

import { useQuery } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { CheckCircleIcon, CopyIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { dateTime } from "@/lib/format";
import { errorMessage, mutate, request } from "@/services/api/client";
import type { Enrollment, EnrollmentCreated, EnrollmentShortCode } from "@/services/api/types";

export interface EnrollmentCodeText {
  /** How to use the code: which app scans it. */
  scan: string;
  waiting: string;
  enrolled: (code: string) => string;
}

/**
 * A created enrollment code, shared by the phone apps (OCM Messages under SMS, OCM Phone under Calls): server-side QR,
 * short code (replaceable, 15 min), link, and the live status polled every 3 s until the phone enrolls.
 */
export function EnrollmentCode({ invite, api, statusKey, text, deviceHref, onEnrolled, onClose }: {
  invite: EnrollmentCreated;
  /** "sms/enrollments" or "calls/enrollments". */
  api: string;
  statusKey: readonly unknown[];
  text: EnrollmentCodeText;
  deviceHref: (id: string) => string;
  onEnrolled: () => void;
  onClose: () => void;
}) {
  const status = useQuery({
    queryKey: statusKey,
    queryFn: () => request<Enrollment>(`${api}/${invite.id}/`),
    refetchInterval: (q) => (q.state.data?.state === "used" ? false : 3000),
  });
  const enrolled = status.data?.state === "used" ? status.data : null;
  const [shortCode, setShortCode] = useState<EnrollmentShortCode | null>(null);
  const short = shortCode ?? { short_code: invite.short_code, short_code_expires_at: invite.short_code_expires_at ?? "" };
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(timer);
  }, []);
  const shortExpired = !!short.short_code_expires_at && new Date(short.short_code_expires_at).getTime() < now;
  const enrolledId = enrolled?.id;
  useEffect(() => {
    if (enrolledId) onEnrolled();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per enrollment
  }, [enrolledId]);

  const copy = async (value: string, what: string) => {
    try { await navigator.clipboard.writeText(value); toast.success(`${what} copied.`); } catch { toast.error("Couldn't copy automatically. Select it and copy it."); }
  };
  const newShortCode = async () => {
    try { setShortCode(await mutate<EnrollmentShortCode>(`${api}/${invite.id}/short-code/`, "POST")); } catch (e) { toast.error(errorMessage(e)); }
  };

  return (
    <div className="mt-4 space-y-5 animate-fade-up" data-enroll-invite="">
      <p className="text-sm text-text-tertiary">{text.scan}</p>
      <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
        <div className="shrink-0 rounded-xl border border-card-border bg-white p-2.5 [&_svg]:size-40" aria-label="QR code for enrolling the phone" role="img"
          dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(invite.qr_svg, { USE_PROFILES: { svg: true } }) }} />
        <div className="w-full min-w-0 space-y-3">
          <span className="block text-xs font-medium text-text-secondary">Short code (type it on the phone)</span>
          <div className="flex items-center gap-2">
            <output data-short-code="" aria-label="Short code" className={`font-mono text-2xl font-semibold tracking-[0.2em] ${shortExpired ? "text-text-tertiary line-through" : "text-text-primary"}`}>{short.short_code}</output>
            <Button appearance="ghost" onPress={newShortCode}>{shortExpired ? "New code" : "Replace"}</Button>
          </div>
          <p className="text-xs text-text-tertiary">{shortExpired ? "This short code expired. Create a new one, or use the QR code." : `Single use · valid until ${dateTime(short.short_code_expires_at)}`}</p>
          <label className="block text-xs font-medium text-text-secondary" htmlFor="enroll-link">Link for the phone (send it in a chat, tap it on the phone)</label>
          <div className="flex gap-2">
            <input id="enroll-link" readOnly value={invite.uri} onFocus={(event) => event.currentTarget.select()}
              className="h-10 min-w-0 flex-1 rounded-lg border border-card-border bg-background-gray-secondary_alt/50 px-3 font-mono text-xs text-text-primary focus:border-primary-500 focus:outline-none" />
            <Button appearance="outline" onPress={() => copy(invite.uri, "Link")} aria-label="Copy link"><CopyIcon size={16} />{m.common.copy}</Button>
          </div>
          <p className="text-xs text-text-tertiary">Works once · expires {dateTime(invite.expires_at)} · {invite.name} · {invite.office.name}</p>
          <p className="text-xs text-text-tertiary">The phone holder sees the company monitoring notice and must accept it before the phone is enrolled.</p>
        </div>
      </div>
      <div role="status" aria-live="polite" className={enrolled ? "flex items-center gap-3 rounded-xl border border-success-500/40 bg-success-500/10 px-4 py-3" : "flex items-center gap-3 rounded-xl border border-card-border bg-background-gray-secondary_alt/40 px-4 py-3"}>
        {enrolled ? <CheckCircleIcon className="text-success-500" /> : <ActivityIndicator size="sm" decorative />}
        <span className="text-sm font-medium text-text-primary">{enrolled ? text.enrolled(enrolled.device?.code ?? "") : text.waiting}</span>
        {enrolled?.device && <Link href={deviceHref(enrolled.device.id)} onClick={onClose} className="ml-auto text-sm font-medium text-primary-500 hover:underline">Open phone</Link>}
      </div>
      {status.data && status.data.failed_attempts > 0 && !enrolled && (
        <p className="text-xs text-warning-700 dark:text-warning-300">{status.data.failed_attempts} failed attempt{status.data.failed_attempts > 1 ? "s" : ""} ({status.data.last_failure}). After 5 the code stops working.</p>
      )}
      <div className="flex justify-end gap-2">
        {!enrolled && <Button appearance="ghost" onPress={async () => { try { await mutate(`${api}/${invite.id}/revoke/`, "POST"); toast("Code revoked."); onClose(); } catch (e) { toast.error(errorMessage(e)); } }}>Revoke code</Button>}
        <Button appearance={enrolled ? "fill" : "outline"} onPress={onClose}>{enrolled ? m.common.done : m.common.close}</Button>
      </div>
    </div>
  );
}

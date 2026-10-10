"use client";

import { useState } from "react";
import { Form } from "react-aria-components";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { Field } from "@/components/ui/field";
import { SelectField } from "@/components/ui/form";
import { CheckCircleIcon, ErrorIcon, LockIcon } from "@/components/ui/icons";
import { ApiError, errorMessage, fieldError, mutate } from "@/services/api/client";
import type { ImapSettings, ImapTestResult } from "@/services/api/types";

type Defaults = { imap_host?: string; imap_port?: number; imap_security?: string; smtp_host?: string; smtp_port?: number; smtp_security?: string };
type Security = ImapSettings["imap_security"];
const SECURITY = [{ value: "ssl", label: "SSL/TLS" }, { value: "starttls", label: "STARTTLS" }];

/**
 * Server settings for a non-Google mailbox (cPanel, Zoho…). Host and ports are prefilled from the MX detection, so most
 * offices only type the normal mailbox password. "Test connection" checks IMAP and SMTP before anything is saved.
 */
export function ImapForm({ mailboxId, email, defaults, onSaved }: { mailboxId: number; email: string; defaults?: Defaults | null; onSaved?: () => void }) {
  const domain = email.split("@")[1] ?? "";
  const [values, setValues] = useState<ImapSettings>({
    imap_host: defaults?.imap_host || `mail.${domain}`, imap_port: defaults?.imap_port || 993, imap_security: (defaults?.imap_security || "ssl") as Security,
    smtp_host: defaults?.smtp_host || `mail.${domain}`, smtp_port: defaults?.smtp_port || 465, smtp_security: (defaults?.smtp_security || "ssl") as Security,
    username: "", password: "",
  });
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState<"test" | "save" | null>(null);
  const [result, setResult] = useState<ImapTestResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const set = (patch: Partial<ImapSettings>) => { setValues((v) => ({ ...v, ...patch })); setResult(null); };

  const run = async (kind: "test" | "save") => {
    setBusy(kind); setError(null);
    try {
      const data = await mutate<ImapTestResult>(`mail/mailboxes/${mailboxId}/${kind === "test" ? "test-imap" : "imap"}/`, "POST", values);
      setResult(data);
      if (kind === "save") { toast.success("Mailbox connected. The first sync has started."); onSaved?.(); }
    } catch (reason) {
      if (reason instanceof ApiError && reason.errors && "imap" in reason.errors) setResult(reason.errors as unknown as ImapTestResult);
      setError(reason);
    } finally { setBusy(null); }
  };

  return (
    <Form className="space-y-4" onSubmit={(event) => { event.preventDefault(); run("save"); }}>
      <Field label="Mailbox password" type="password" autoComplete="new-password" value={values.password} onChange={(password) => set({ password })} isRequired
        error={fieldError(error, "password")} />
      <p className="-mt-2 flex items-center gap-1.5 text-xs text-text-tertiary"><LockIcon size={13} /> The normal email password. It is stored encrypted and never shown again.</p>

      <button type="button" onClick={() => setAdvanced((v) => !v)} aria-expanded={advanced} className="text-sm font-medium text-primary-500 hover:underline">
        {advanced ? "Hide server settings" : `Server settings (${values.imap_host})`}
      </button>
      {advanced && (
        <div className="grid gap-4 rounded-xl border border-card-border bg-background-gray-secondary_alt/30 p-4 sm:grid-cols-2">
          <Field label="Username" placeholder={email} value={values.username} onChange={(username) => set({ username })} />
          <div className="hidden sm:block" />
          <Field label="Incoming (IMAP) server" value={values.imap_host} onChange={(imap_host) => set({ imap_host })} isRequired error={fieldError(error, "imap_host")} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Port" inputMode="numeric" value={String(values.imap_port)} onChange={(v) => set({ imap_port: Number(v) || 0 })} isRequired />
            <SelectField label="Security" value={values.imap_security} onChange={(e) => set({ imap_security: e.target.value as ImapSettings["imap_security"] })} options={SECURITY} />
          </div>
          <Field label="Outgoing (SMTP) server" value={values.smtp_host} onChange={(smtp_host) => set({ smtp_host })} isRequired error={fieldError(error, "smtp_host")} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Port" inputMode="numeric" value={String(values.smtp_port)} onChange={(v) => set({ smtp_port: Number(v) || 0 })} isRequired />
            <SelectField label="Security" value={values.smtp_security} onChange={(e) => {
              const smtp_security = e.target.value as ImapSettings["smtp_security"];
              set({ smtp_security, smtp_port: smtp_security === "starttls" && values.smtp_port === 465 ? 587 : smtp_security === "ssl" && values.smtp_port === 587 ? 465 : values.smtp_port });
            }} options={SECURITY} />
          </div>
        </div>
      )}

      {result && (
        <ul aria-live="polite" className="space-y-1.5 rounded-xl border border-card-border p-3 text-sm">
          {(["imap", "smtp"] as const).map((key) => (
            <li key={key} className="flex items-start gap-2">
              {result[key]?.ok ? <CheckCircleIcon size={18} className="shrink-0 text-success-500" /> : <ErrorIcon size={18} className="shrink-0 text-error-500" />}
              <span><b>{key === "imap" ? "Receiving (IMAP)" : "Sending (SMTP)"}:</b> {result[key]?.message}</span>
            </li>
          ))}
        </ul>
      )}
      {!!error && !result && <p role="alert" className="text-sm text-error-500">{errorMessage(error)}</p>}

      <div className="flex flex-wrap gap-2">
        <Button appearance="outline" onPress={() => run("test")} isPending={busy === "test"} isDisabled={!values.password || !!busy}>Test connection</Button>
        <Button type="submit" isPending={busy === "save"} isDisabled={!values.password || !!busy}>Save &amp; connect</Button>
      </div>
    </Form>
  );
}

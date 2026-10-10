"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Form } from "react-aria-components";
import { ME_KEY, useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { ButtonLink } from "@/components/tailgrids/core/button-link";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { Field } from "@/components/ui/field";
import { SelectField, SwitchRow } from "@/components/ui/form";
import { BuildingIcon, CheckCircleIcon, GlobeIcon, GoogleIcon, InfoIcon, LinkIcon, LockIcon, WarningIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage, fieldError, mutate, request } from "@/services/api/client";
import type { Detection, MailboxCreated, MailSettings, Office } from "@/services/api/types";
import { mailKeys } from "@/platforms/gmail/api/keys";
import { ConnectLinkDialog } from "@/platforms/gmail/components/mailboxes/connect-link-dialog";
import { ImapForm } from "@/platforms/gmail/components/mailboxes/imap-form";
import { cn } from "@/utils/cn";

const STEPS = ["Office & email", "Connection method", "Connect"];

const METHOD: Record<string, { icon: React.ReactNode; title: string; sentence: string }> = {
  gmail_oauth: { icon: <GoogleIcon />, title: "Google sign-in", sentence: "This is a Google mailbox. The office person opens a link, chooses the account and taps Allow. No passwords are shared." },
  workspace_delegation: { icon: <BuildingIcon />, title: "Company Google Workspace", sentence: "Your company has authorised Communication Manager for this domain, so the mailbox connects instantly with no sign-in." },
  imap_smtp: { icon: <GlobeIcon />, title: "Email server (IMAP/SMTP)", sentence: "This mailbox is hosted outside Google. Connect it with the normal email password; the server settings are filled in for you." },
  fake: { icon: <InfoIcon />, title: "Demo mailbox", sentence: "A sample mailbox filled with realistic mail, for trying the workspace without real credentials." },
  unsupported: { icon: <WarningIcon />, title: "Not supported yet", sentence: "" },
};

export default function NewMailboxPage() {
  usePageTitle({ page: "Add mailbox", section: "Mailboxes" });
  const { can } = useSession();
  const router = useRouter();
  const client = useQueryClient();
  const offices = useQuery({ queryKey: ["settings", "offices"], queryFn: () => request<Office[]>("settings/offices/"), staleTime: 60_000 });
  const settings = useQuery({ queryKey: ["settings", "integrations"], queryFn: () => request<MailSettings>("settings/integrations/"), staleTime: 60_000 });

  const [step, setStep] = useState(0);
  const [pickedOffice, setOffice] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [demo, setDemo] = useState(false);
  const [detection, setDetection] = useState<Detection | null>(null);
  const [created, setCreated] = useState<MailboxCreated | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [linkOpen, setLinkOpen] = useState(false);

  const office = pickedOffice || String(offices.data?.[0]?.id ?? "");

  if (!can("mail.manage_mailboxes")) return <Page><PageHeader title="Add mailbox" description="You don't have permission to add mailboxes. Ask an administrator." /></Page>;

  const detect = async () => {
    setBusy(true); setError(null);
    try {
      const result = demo ? { provider: "fake", reason: "", domain: email.split("@")[1] ?? "", mx: [], supported: true, imap_defaults: null } as Detection
        : await mutate<Detection>("mail/mailboxes/detect/", "POST", { email });
      setDetection(result); setStep(1);
    } catch (reason) { setError(reason); } finally { setBusy(false); }
  };

  const create = async () => {
    setBusy(true); setError(null);
    try {
      const data = await mutate<MailboxCreated>("mail/mailboxes/", "POST", { office: Number(office), email, display_name: displayName, provider: demo ? "fake" : "auto" });
      setCreated(data); setStep(2);
      client.invalidateQueries({ queryKey: mailKeys.mailboxes() });
      client.invalidateQueries({ queryKey: ME_KEY });
    } catch (reason) { setError(reason); } finally { setBusy(false); }
  };

  const connectNow = async () => {
    if (!created) return;
    setBusy(true); setError(null);
    try {
      const { url } = await mutate<{ url: string }>(`mail/mailboxes/${created.mailbox.id}/connect/`, "POST");
      window.location.assign(url);
    } catch (reason) { setError(reason); setBusy(false); }
  };

  const method = METHOD[detection?.provider ?? "gmail_oauth"];
  const box = created?.mailbox;

  return (
    <Page className="max-w-3xl">
      <PageHeader eyebrow="Mailboxes" title="Add a mailbox" description="Connect an office mailbox in three short steps." />
      <ol className="mb-5 flex items-center gap-2 text-xs sm:text-sm" aria-label="Progress">
        {STEPS.map((label, index) => (
          <li key={label} className="flex min-w-0 flex-1 items-center gap-2" aria-current={index === step ? "step" : undefined}>
            <span className={cn("flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
              index < step ? "bg-success-500 text-white" : index === step ? "bg-primary-500 text-white" : "bg-background-gray-secondary_alt text-text-tertiary")}>
              {index < step ? "✓" : index + 1}
            </span>
            <span className={cn("truncate", index === step ? "font-medium text-text-primary" : "text-text-tertiary")}>{label}</span>
            {index < STEPS.length - 1 && <span className="hidden h-px flex-1 bg-card-border sm:block" aria-hidden="true" />}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <SectionCard padding="md">
          <Form className="space-y-4" onSubmit={(event) => { event.preventDefault(); detect(); }}>
            {offices.data && offices.data.length === 0 ? (
              <p className="rounded-lg border border-warning-500/40 bg-warning-500/10 p-3 text-sm">No offices exist yet. <Link href="/settings/offices" className="font-semibold underline">Create an office</Link> first.</p>
            ) : (
              <SelectField label="Office" value={office} onChange={(e) => setOffice(e.target.value)} required
                options={(offices.data ?? []).map((o) => ({ value: String(o.id), label: o.name }))} hint={<>Missing one? <Link href="/settings/offices" className="text-primary-500 hover:underline">Manage offices</Link></>} />
            )}
            <Field label="Email address" type="email" value={email} onChange={(v) => { setEmail(v); setDetection(null); }} isRequired autoFocus placeholder="finance.office@gmail.com" error={fieldError(error, "email")} />
            <Field label="Display name (optional)" value={displayName} onChange={setDisplayName} placeholder="Finance office" />
            {settings.data?.fake_provider_enabled && (
              <div className="rounded-lg border border-dashed border-card-border px-3"><SwitchRow title="Demo mailbox" description="Fill it with sample mail instead of connecting a real account." checked={demo} onChange={setDemo} /></div>
            )}
            {!!error && !fieldError(error, "email") && <p role="alert" className="text-sm text-error-500">{errorMessage(error)}</p>}
            <div className="flex justify-end gap-2 pt-1">
              <ButtonLink appearance="outline" href="/gmail/mailboxes">Cancel</ButtonLink>
              <Button type="submit" isPending={busy} isDisabled={busy || !email || !office}>Continue</Button>
            </div>
          </Form>
        </SectionCard>
      )}

      {step === 1 && detection && (
        <SectionCard>
          <div className={cn("flex items-start gap-4 rounded-xl border p-4", detection.supported ? "border-primary-500/30 bg-primary-500/5" : "border-warning-500/40 bg-warning-500/10")}>
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-card-surface-area text-primary-500 shadow-xs [&_svg]:size-6">{method.icon}</span>
            <div className="min-w-0">
              <p className="text-xs font-medium tracking-wide text-text-tertiary uppercase">Detected for {detection.domain}</p>
              <h2 className="mt-0.5 font-semibold text-text-primary">{method.title}</h2>
              <p className="mt-1 text-sm text-text-secondary">{detection.supported ? method.sentence : detection.reason}</p>
            </div>
          </div>
          {!!error && <p role="alert" className="mt-4 text-sm text-error-500">{errorMessage(error)}</p>}
          <div className="mt-5 flex justify-end gap-2">
            <Button appearance="outline" onPress={() => { setStep(0); setError(null); }}>Back</Button>
            {detection.supported && <Button onPress={create} isPending={busy} isDisabled={busy}>Add mailbox</Button>}
          </div>
        </SectionCard>
      )}

      {step === 2 && box && (
        <SectionCard>
          {box.status === "connected" || box.status === "syncing" ? (
            <div className="flex flex-col items-center py-8 text-center">
              <CheckCircleIcon size={48} className="text-success-500" />
              <h2 className="mt-3 text-lg font-semibold">{box.email} is connected</h2>
              <p className="mt-1 text-sm text-text-tertiary">The inbox is syncing now. It will appear in the mailbox switcher in a moment.</p>
              <div className="mt-5 flex gap-2"><ButtonLink appearance="outline" href="/gmail/mailboxes">All mailboxes</ButtonLink><ButtonLink href={`/gmail/mailboxes/${box.id}`}>Mailbox settings</ButtonLink></div>
            </div>
          ) : box.provider === "imap_smtp" ? (
            <>
              <h2 className="font-semibold">Connect {box.email}</h2>
              <p className="mt-1 mb-4 text-sm text-text-tertiary">Enter the mailbox password. We test it before saving.</p>
              <ImapForm mailboxId={box.id} email={box.email} defaults={detection?.imap_defaults} onSaved={() => router.push(`/gmail/mailboxes/${box.id}`)} />
            </>
          ) : (
            <>
              <h2 className="font-semibold">How would you like to connect {box.email}?</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <ChoiceCard icon={<GoogleIcon />} title="Connect now" body="You are with the office person, or you can sign in to this account yourself." onPress={connectNow} busy={busy} />
                <ChoiceCard icon={<LinkIcon />} title="Send connect link" body="Share a single-use link by WhatsApp, copy or QR code. Valid for 72 hours." onPress={() => setLinkOpen(true)} primary />
              </div>
              {!!error && <p role="alert" className="mt-4 text-sm text-error-500">{errorMessage(error)}</p>}
              {!settings.data?.google_configured && settings.data && (
                <p className="mt-4 flex items-start gap-2 rounded-lg border border-warning-500/40 bg-warning-500/10 p-3 text-sm"><WarningIcon size={18} className="shrink-0 text-warning-500" />Google sign-in is not configured on this server yet. See docs/google-setup.md.</p>
              )}
              <p className="mt-4 flex items-center gap-1.5 text-xs text-text-tertiary"><LockIcon size={13} /> Access tokens are encrypted and every mailbox access is logged.</p>
              <div className="mt-5 flex justify-end"><ButtonLink appearance="ghost" href={`/gmail/mailboxes/${box.id}`}>Do this later</ButtonLink></div>
              <ConnectLinkDialog mailboxId={box.id} email={box.email} isOpen={linkOpen} onOpenChange={setLinkOpen} />
            </>
          )}
        </SectionCard>
      )}
      {step === 0 && offices.isPending && <div className="mt-4 flex justify-center"><ActivityIndicator size="sm" label="Loading offices" /></div>}
    </Page>
  );
}

function ChoiceCard({ icon, title, body, onPress, busy, primary }: { icon: React.ReactNode; title: string; body: string; onPress: () => void; busy?: boolean; primary?: boolean }) {
  return (
    <button type="button" onClick={onPress} disabled={busy}
      className={cn("flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition hover:border-primary-500 hover:bg-primary-500/5 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none disabled:opacity-60",
        primary ? "border-primary-500/40 bg-primary-500/5" : "border-card-border")}>
      <span className="flex size-10 items-center justify-center rounded-lg bg-card-surface-area text-primary-500 shadow-xs [&_svg]:size-5">{busy ? <ActivityIndicator size="sm" decorative /> : icon}</span>
      <span className="font-semibold text-text-primary">{title}</span>
      <span className="text-sm text-text-tertiary">{body}</span>
    </button>
  );
}

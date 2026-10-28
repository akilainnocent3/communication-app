"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field } from "@/components/ui/field";
import { TextAreaField } from "@/components/ui/form";
import { CheckCircleIcon, CopyIcon, ErrorIcon, GoogleIcon, TrashIcon, UploadIcon, WarningIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { StatusPill } from "@/components/ui/status-pill";
import { dateTime } from "@/lib/format";
import { errorMessage, fieldError, mutate, request } from "@/services/api/client";
import type { MailSettings, WorkspaceDomain } from "@/services/api/types";
import { SmsNoticeCard } from "@/platforms/sms/components/tools/settings-card";

const KEY = ["settings", "integrations"] as const;
const WORKSPACE = ["settings", "workspace"] as const;

async function copy(text: string, what: string) {
  try { await navigator.clipboard.writeText(text); toast.success(`${what} copied.`); } catch { toast.error("Couldn't copy. Select the text and copy it."); }
}

function CopyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="mb-1 text-xs font-medium text-text-tertiary">{label}</p>
      <div className="flex items-start gap-2">
        <code className="min-w-0 flex-1 rounded-lg border border-card-border bg-background-gray-secondary_alt/50 px-3 py-2 font-mono text-xs break-all text-text-primary">{value}</code>
        <Button size="sm" appearance="outline" iconOnly aria-label={`Copy ${label}`} onPress={() => copy(value, label)}><CopyIcon size={15} /></Button>
      </div>
    </div>
  );
}

export default function IntegrationsPage() {
  usePageTitle({ page: "Integrations", section: "Settings" });
  const { can, isSuperAdmin } = useSession();
  const mail = can("mail.manage_mailboxes");
  const sms = can("sms.manage_devices");
  const settings = useQuery({ queryKey: KEY, queryFn: () => request<MailSettings>("settings/integrations/"), enabled: mail });
  if (!mail && !sms) return <Page><PageHeader title="Integrations" description="You don't have permission to change integrations." /></Page>;
  return (
    <Page className="max-w-4xl">
      <PageHeader title="Integrations" description="How OCM connects to Google, other mail services and company phones." />
      <div className="space-y-4 sm:space-y-5">
        {mail && (settings.isPending ? <PageSkeleton /> : settings.error ? <RequestState loading={false} error={errorMessage(settings.error)} onRetry={() => settings.refetch()} /> : (
          <>
            <GoogleOAuth data={settings.data!} />
            <ConnectNotice data={settings.data!} />
            {isSuperAdmin && <Workspace />}
          </>
        ))}
        {sms && <SmsNoticeCard />}
      </div>
    </Page>
  );
}

function GoogleOAuth({ data }: { data: MailSettings }) {
  return (
    <SectionCard title={<span className="flex items-center gap-2"><GoogleIcon size={18} />Google sign-in (OAuth)</span>}
      description="Used for @gmail.com mailboxes and Google Workspace mailboxes connected one by one."
      actions={data.google_configured ? <StatusPill tone="success">Configured</StatusPill> : <StatusPill tone="warning">Not configured</StatusPill>}>
      {!data.google_configured && (
        <p className="mb-4 flex items-start gap-2 rounded-lg border border-warning-500/40 bg-warning-500/10 p-3 text-sm">
          <WarningIcon size={18} className="shrink-0 text-warning-500" />Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET on the server. docs/google-setup.md walks through it step by step.
        </p>
      )}
      <div className="grid gap-4">
        <CopyValue label="Authorised redirect URI (paste in Google Cloud → Credentials)" value={data.redirect_uri} />
        <CopyValue label="Scopes" value={data.scopes.join(" ")} />
      </div>
    </SectionCard>
  );
}

function ConnectNotice({ data }: { data: MailSettings }) {
  const client = useQueryClient();
  const [text, setText] = useState(data.connect_notice);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try { client.setQueryData(KEY, await mutate<MailSettings>("settings/integrations/", "PUT", { connect_notice: text })); toast.success("Notice saved."); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <SectionCard title="Connect page notice" description="Shown to staff on the public connect page before they allow access. Supports the company's duties under Tanzania's Personal Data Protection Act."
      footer={<div className="flex justify-end"><Button onPress={save} isPending={busy} isDisabled={!text.trim() || text === data.connect_notice}>Save notice</Button></div>}>
      <TextAreaField label="Notice" value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={2000} />
    </SectionCard>
  );
}

function Workspace() {
  const client = useQueryClient();
  const domains = useQuery({ queryKey: WORKSPACE, queryFn: () => request<WorkspaceDomain[]>("settings/integrations/workspace/") });
  const [domain, setDomain] = useState("");
  const [json, setJson] = useState("");
  const [fileName, setFileName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const save = async () => {
    setBusy(true); setError(null);
    try {
      await mutate("settings/integrations/workspace/", "POST", { domain, service_account_json: json });
      client.invalidateQueries({ queryKey: WORKSPACE });
      setDomain(""); setJson(""); setFileName("");
      toast.success("Service account saved. Now authorise it in Google Admin and press Test.");
    } catch (e) { setError(e); } finally { setBusy(false); }
  };

  return (
    <SectionCard title="Google Workspace: company-wide access (optional)"
      description="Connect every mailbox in a company domain with zero clicks per mailbox. A Workspace admin authorises OCM once.">
      {domains.isPending || domains.error ? <RequestState loading={domains.isPending} error={errorMessage(domains.error)} onRetry={() => domains.refetch()} /> : (
        <div className="space-y-4">
          {domains.data!.map((row) => <DomainCard key={row.id} row={row} />)}
          <div className="rounded-xl border border-dashed border-card-border p-4">
            <h3 className="mb-3 text-sm font-semibold">{domains.data!.length ? "Add another domain" : "Add a domain"}</h3>
            <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm text-text-secondary">
              <li>In Google Cloud, create a service account and download its JSON key.</li>
              <li>Upload it here with the company domain.</li>
              <li>Paste the Client ID and scopes shown into Google Admin → Security → API controls → Domain-wide delegation, then press Test.</li>
            </ol>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Domain" value={domain} onChange={setDomain} placeholder="company.com" error={fieldError(error, "domain")} />
              <div className="flex min-w-0 flex-col gap-2 text-sm">
                <span className="font-medium">Service-account key (JSON)</span>
                <label className="flex h-10.5 cursor-pointer items-center gap-2 rounded-lg border border-card-border bg-input-background px-3 text-text-secondary focus-within:ring-2 focus-within:ring-primary-500 hover:border-primary-500">
                  <UploadIcon size={16} /><span className="truncate">{fileName || "Choose file…"}</span>
                  <input type="file" accept="application/json,.json" className="sr-only" onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setFileName(file.name); setJson(await file.text());
                  }} />
                </label>
                {fieldError(error, "service_account_json") && <span className="text-xs text-error-500">{fieldError(error, "service_account_json")}</span>}
              </div>
            </div>
            {!!error && !fieldError(error, "domain") && !fieldError(error, "service_account_json") && <p role="alert" className="mt-3 text-sm text-error-500">{errorMessage(error)}</p>}
            <div className="mt-4 flex justify-end"><Button onPress={save} isPending={busy} isDisabled={!domain || !json}>Save key</Button></div>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

function DomainCard({ row }: { row: WorkspaceDomain }) {
  const client = useQueryClient();
  const [email, setEmail] = useState(`info@${row.domain}`);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const test = async () => {
    setBusy(true);
    try {
      const data = await mutate<WorkspaceDomain>(`settings/integrations/workspace/${row.id}/test/`, "POST", { email });
      client.setQueryData<WorkspaceDomain[]>(WORKSPACE, (rows) => rows?.map((r) => (r.id === row.id ? data : r)));
      if (data.last_test_ok) toast.success(`It works: ${email} can be connected instantly.`); else toast.error(data.last_test_error || "The test failed.");
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-xl border border-card-border p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="font-semibold text-text-primary">{row.domain}</h3>
        {row.last_test_at ? (row.last_test_ok ? <StatusPill tone="success">Working</StatusPill> : <StatusPill tone="error">Test failed</StatusPill>) : <StatusPill tone="warning">Not tested</StatusPill>}
        <Button size="sm" appearance="ghost" iconOnly aria-label={`Remove ${row.domain}`} className="ml-auto" onPress={() => setConfirm(true)}><TrashIcon size={16} /></Button>
      </div>
      <div className="grid gap-3">
        <CopyValue label="Client ID" value={row.client_id} />
        <CopyValue label="OAuth scopes (paste exactly)" value={row.scopes} />
      </div>
      {row.last_test_at && (
        <p className={`mt-3 flex items-start gap-2 text-sm ${row.last_test_ok ? "text-success-600 dark:text-success-400" : "text-error-500"}`}>
          {row.last_test_ok ? <CheckCircleIcon size={16} className="mt-0.5 shrink-0" /> : <ErrorIcon size={16} className="mt-0.5 shrink-0" />}
          {row.last_test_ok ? `Last test passed ${dateTime(row.last_test_at)}.` : row.last_test_error}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <div className="w-full max-w-xs"><Field label="Test with a mailbox" type="email" value={email} onChange={setEmail} /></div>
        <Button appearance="outline" onPress={test} isPending={busy}>Test</Button>
      </div>
      <ConfirmDialog isOpen={confirm} onOpenChange={setConfirm} title={`Remove ${row.domain}?`} confirmLabel="Remove" body="Mailboxes already connected this way will stop syncing until they are reconnected with Google sign-in."
        onConfirm={async () => {
          try { await mutate(`settings/integrations/workspace/${row.id}/`, "DELETE"); client.invalidateQueries({ queryKey: WORKSPACE }); toast("Domain removed."); }
          catch (e) { toast.error(errorMessage(e)); throw e; }
        }} />
    </div>
  );
}

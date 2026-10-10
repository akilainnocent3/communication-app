"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { CheckCircleIcon, ChevronDownIcon, ErrorIcon, LockIcon, ShieldIcon, WarningIcon } from "@/components/ui/icons";
import { ApiError, errorMessage, mutate, request } from "@/services/api/client";
import type { PublicInvite } from "@/services/api/types";
import { connectResult } from "@/platforms/gmail/components/mailboxes/connect-results";
import { ConnectFrame, GoogleButton } from "../connect-ui";
import { cn } from "@/utils/cn";

export default function ConnectPage() {
  return <Suspense fallback={<ConnectFrame><Loading /></ConnectFrame>}><Connect /></Suspense>;
}

function Loading() {
  return <div className="flex justify-center py-16"><ActivityIndicator label="Loading" /></div>;
}

function Connect() {
  const { token } = useParams<{ token: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState("");
  const invite = useQuery({ queryKey: ["connect", token], queryFn: () => request<PublicInvite>(`mail/connect/${encodeURIComponent(token)}/`), retry: false });
  const code = params.get("result");
  const result = connectResult(code, params, invite.data?.mailbox_email);

  const start = async () => {
    setBusy(true); setStartError("");
    try {
      const { url } = await mutate<{ url: string }>("mail/oauth/start/", "POST", { token });
      window.location.assign(url);
    } catch (error) { setStartError(errorMessage(error)); setBusy(false); }
  };

  if (invite.isPending) return <ConnectFrame><Loading /></ConnectFrame>;
  if (invite.error || !invite.data) {
    const missing = invite.error instanceof ApiError && invite.error.status === 404;
    return (
      <ConnectFrame>
        <Outcome tone="error" title={missing ? "This link is not valid" : "Couldn't open this link"}
          body={missing ? "Check that you copied the whole link, or ask your administrator for a new one." : errorMessage(invite.error)} />
      </ConnectFrame>
    );
  }
  const data = invite.data;

  if (data.state === "connected" || code === "connected") {
    return (
      <ConnectFrame company={data.company_name}>
        <Outcome tone="success" title="Mailbox connected" body={<>You can close this page. <span className="font-medium text-text-primary">{data.mailbox_email}</span> is now linked to {data.company_name}.</>} />
      </ConnectFrame>
    );
  }
  if (data.state !== "active") {
    return (
      <ConnectFrame company={data.company_name}>
        <Outcome tone="error" title={data.state === "revoked" ? "This link was cancelled" : "This link has expired"} body="For safety, connect links work once and for 72 hours. Ask your administrator to send a new one." />
      </ConnectFrame>
    );
  }

  return (
    <ConnectFrame company={data.company_name}>
      {result && result.tone !== "success" && (
        <div role="alert" className={cn("mb-6 flex items-start gap-3 rounded-xl border p-4 text-sm", result.tone === "warning" ? "border-warning-500/40 bg-warning-500/10" : "border-error-500/40 bg-error-500/10")}>
          {result.tone === "warning" ? <WarningIcon className="shrink-0 text-warning-500" /> : <ErrorIcon className="shrink-0 text-error-500" />}
          <div><p className="font-semibold text-text-primary">{result.title}</p><p className="mt-0.5 text-text-secondary">{result.body}</p></div>
        </div>
      )}
      <h1 className="text-2xl leading-snug font-semibold text-text-primary sm:text-[28px]">
        {data.company_name} wants to connect the mailbox <span className="break-all text-primary-500 dark:text-primary-300">{data.mailbox_email}</span> to Communication Manager.
      </h1>

      <div className="mt-6 flex gap-3 rounded-xl border border-card-border bg-background-gray-secondary_alt/40 p-4 text-sm text-text-secondary">
        <ShieldIcon className="mt-0.5 shrink-0 text-primary-500" />
        <p className="whitespace-pre-line">{data.notice}</p>
      </div>

      <div className="mt-8">
        {data.google_configured ? (
          <GoogleButton onPress={start} busy={busy} label={result?.retry ? "Try again with Google" : "Continue with Google"} />
        ) : (
          <p className="rounded-xl border border-warning-500/40 bg-warning-500/10 p-4 text-sm">Google sign-in is not set up on this server yet. Tell your administrator.</p>
        )}
        {startError && <p role="alert" className="mt-3 text-sm text-error-500">{startError}</p>}
        <p className="mt-3 text-center text-xs text-text-tertiary">Choose <b className="text-text-secondary">{data.mailbox_email}</b> on the next screen, then tap <b className="text-text-secondary">Allow</b>.</p>
      </div>

      <UnverifiedHelp />

      <p className="mt-8 flex items-center justify-center gap-1.5 text-xs text-text-tertiary"><LockIcon size={13} /> Your password is never shared. You can remove access any time in your Google account.</p>
      {code && <button type="button" className="sr-only" onClick={() => router.replace(`/connect/${token}`)}>Clear message</button>}
    </ConnectFrame>
  );
}

function UnverifiedHelp() {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-6 rounded-xl border border-card-border">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 rounded-xl px-4 py-3 text-left text-sm font-medium text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
        <span className="flex items-center gap-2"><WarningIcon size={16} className="text-warning-500" />Seeing “Google hasn’t verified this app”?</span>
        <ChevronDownIcon className={cn("shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-4 border-t border-card-border px-4 py-4 text-sm text-text-secondary">
          <p>This is expected: the app is private to your company. It is safe to continue.</p>
          <ol className="list-decimal space-y-1 pl-5">
            <li>Tap <b className="text-text-primary">Advanced</b> (bottom left).</li>
            <li>Tap <b className="text-text-primary">Go to Communication Manager (unsafe)</b>.</li>
            <li>Leave every box ticked and tap <b className="text-text-primary">Allow</b>.</li>
          </ol>
          {/* Small illustration of Google's warning screen with the two taps highlighted. */}
          <div aria-hidden="true" className="mx-auto max-w-xs rounded-lg border border-zinc-200 bg-white p-4 text-[11px] text-zinc-700 shadow-sm">
            <div className="mb-2 flex items-center gap-1.5"><span className="size-3 rounded-full bg-[#4285F4]" /><span className="font-medium text-zinc-800">Google</span></div>
            <p className="text-sm font-medium text-zinc-900">Google hasn’t verified this app</p>
            <p className="mt-1 text-zinc-500">The app is requesting access to sensitive info in your Google Account…</p>
            <div className="mt-3 flex items-center justify-between">
              <span className="rounded px-1.5 py-0.5 font-medium text-[#1a73e8] ring-2 ring-warning-500">Advanced ①</span>
              <span className="rounded bg-[#1a73e8] px-2 py-1 font-medium text-white">Back to safety</span>
            </div>
            <p className="mt-3 border-t border-zinc-100 pt-2"><span className="rounded px-1 font-medium text-[#1a73e8] underline ring-2 ring-warning-500">Go to Communication Manager (unsafe) ②</span></p>
          </div>
        </div>
      )}
    </div>
  );
}

function Outcome({ tone, title, body }: { tone: "success" | "error"; title: string; body: React.ReactNode }) {
  return (
    <div role="status" className="flex flex-col items-center py-10 text-center animate-fade-up">
      <span className={cn("flex size-20 items-center justify-center rounded-full", tone === "success" ? "bg-success-500/12 text-success-500" : "bg-error-500/10 text-error-500")}>
        {tone === "success" ? <CheckCircleIcon size={48} /> : <ErrorIcon size={44} />}
      </span>
      <h1 className="mt-5 text-2xl font-semibold text-text-primary">{title}</h1>
      <p className="mt-2 max-w-sm text-sm text-text-secondary">{body}</p>
    </div>
  );
}

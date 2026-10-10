"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Form } from "react-aria-components";
import { BrandLogo, BrandMark } from "@/components/shell/brand";
import { ME_KEY, fetchMe } from "@/components/shell/session-provider";
import ThemeToggle from "@/components/shell/theme-toggle";
import { Field } from "@/components/ui/field";
import { MailIcon, MediaIcon, MessageIcon, PhoneIcon, ShieldIcon } from "@/components/ui/icons";
import { Button } from "@/components/tailgrids/core/button";
import { m } from "@/i18n";
import { safeNext } from "@/lib/safe-next";
import { ApiError, errorMessage, mutate } from "@/services/api/client";
import type { Me } from "@/services/api/types";

const CHANNELS = [
  { icon: <MailIcon />, name: m.platforms.gmail.name, live: true },
  { icon: <MessageIcon />, name: m.platforms.sms.name, live: false },
  { icon: <PhoneIcon />, name: m.platforms.calls.name, live: false },
  { icon: <MediaIcon />, name: m.platforms.media.name, live: false },
];

export default function LoginPage() {
  const router = useRouter();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [needsOtp, setNeedsOtp] = useState(false);
  const [expired] = useState(() => typeof window !== "undefined" && new URLSearchParams(window.location.search).has("expired"));
  const me = useQuery({ queryKey: ME_KEY, queryFn: fetchMe, retry: false });

  useEffect(() => {
    if (me.data) router.replace(safeNext(new URLSearchParams(window.location.search).get("next")) ?? "/");
  }, [me.data, router]);

  return (
    <main className="grid h-full overflow-y-auto bg-card-surface-area text-text-primary lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <section className="flex min-h-full flex-col px-5 py-6 sm:px-10 lg:px-14">
        <header className="flex items-center justify-between gap-4">
          <BrandLogo size={36} />
          <ThemeToggle />
        </header>

        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-sm animate-fade-up">
            <p className="mb-3 text-xs font-semibold tracking-[0.18em] text-primary-500 uppercase dark:text-primary-300">Admin workspace</p>
            <h1 className="text-3xl leading-tight font-semibold sm:text-[34px]">Welcome back</h1>
            <p className="mt-2 text-sm text-text-tertiary">{m.auth.subtitle}</p>
            {expired && !error && (
              <p role="status" className="mt-6 rounded-lg border border-warning-500/40 bg-warning-500/10 px-3 py-2.5 text-sm text-text-primary">{m.auth.sessionExpired}</p>
            )}
            {/* method="post": a submit before hydration must never put the password in the URL. */}
            <Form
              method="post"
              className="mt-8 space-y-5"
              onSubmit={async (event) => {
                event.preventDefault();
                if (busy) return;
                const values = new FormData(event.currentTarget);
                setBusy(true);
                setError("");
                try {
                  const data = await mutate<Me>("auth/login/", "POST", {
                    email: String(values.get("email")),
                    password: String(values.get("password")),
                    otp: needsOtp ? String(values.get("otp") || "") : undefined,
                  });
                  client.setQueryData(ME_KEY, data);
                } catch (reason) {
                  if (reason instanceof ApiError && (reason.code === "otp_required" || reason.code === "otp_invalid")) setNeedsOtp(true);
                  setError(errorMessage(reason));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <Field label={m.auth.email} name="email" type="email" autoComplete="username" autoFocus isRequired isDisabled={busy} />
              <Field label={m.auth.password} name="password" type="password" autoComplete="current-password" isRequired isDisabled={busy} />
              {needsOtp && (
                <Field label={m.auth.otp} name="otp" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" autoFocus isRequired isDisabled={busy} />
              )}
              {error && <p role="alert" className="rounded-lg border border-error-500/40 bg-error-500/10 px-3 py-2.5 text-sm text-error-500">{error}</p>}
              <Button type="submit" size="lg" isPending={busy} isDisabled={busy} className="h-12 w-full">
                {busy ? m.auth.submitting : m.auth.submit}
              </Button>
            </Form>
            <p className="mt-6 text-xs text-text-tertiary">Accounts are created by your administrator. Contact them if you cannot sign in.</p>
          </div>
        </div>

        <footer className="text-xs text-text-tertiary">© {new Date().getFullYear()} {m.brand.name}</footer>
      </section>

      {/* Decorative brand panel (desktop only): the channels this workspace brings together. */}
      <aside aria-hidden="true" className="relative hidden overflow-hidden bg-[#050b24] text-white lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:44px_44px] [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />
        <div className="pointer-events-none absolute -top-40 -right-32 size-[520px] rounded-full bg-[#3758f9]/35 blur-[120px]" />
        <div className="pointer-events-none absolute -bottom-48 -left-24 size-[440px] rounded-full bg-[#22d3ee]/15 blur-[120px]" />

        <div className="relative flex items-center gap-3">
          <BrandMark size={44} />
          <span className="text-sm font-medium text-white/80">{m.brand.name}</span>
        </div>

        <div className="relative max-w-lg">
          <h2 className="text-4xl leading-tight font-semibold xl:text-[44px]">Every office inbox, one calm workspace.</h2>
          <p className="mt-4 text-base text-white/65">Read, reply and organise mail for every office as if you were in Gmail, with every access logged.</p>

          <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.04] p-5 shadow-2xl backdrop-blur">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-white/85">Channels</span>
              <span className="flex gap-1.5"><span className="size-2 rounded-full bg-white/25" /><span className="size-2 rounded-full bg-white/25" /><span className="size-2 rounded-full bg-[#3758f9]" /></span>
            </div>
            <ul className="mt-5 space-y-2.5">
              {[["Head Office", "info@", 12], ["Finance", "finance@", 4], ["Arusha branch", "arusha.office@", 7]].map(([office, email, unread], index) => (
                <li key={String(office)} className="flex items-center gap-3 rounded-xl bg-white/[0.05] px-3.5 py-3" style={{ opacity: 1 - index * 0.15 }}>
                  <span className="flex size-8 items-center justify-center rounded-full bg-[#3758f9]/40 text-xs font-semibold">{String(office)[0]}</span>
                  <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{office}</span><span className="block text-xs text-white/55">{email}…</span></span>
                  <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs tabular-nums">{unread}</span>
                </li>
              ))}
            </ul>
            <ul className="mt-5 grid grid-cols-4 gap-2 text-xs text-white/75">
              {CHANNELS.map((channel) => (
                <li key={channel.name} className="flex flex-col items-center gap-1.5 rounded-lg bg-white/[0.05] px-2 py-2.5">
                  <span className={channel.live ? "text-[#93b4ff]" : "text-white/40"}>{channel.icon}</span>
                  {channel.name}
                  {!channel.live && <span className="text-[10px] text-white/40">{m.common.soon}</span>}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="relative flex items-center gap-2 text-xs text-white/45"><ShieldIcon size={14} /> Session sign-in · Role-based access · Every mailbox access audited</p>
      </aside>
    </main>
  );
}

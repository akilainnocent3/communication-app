"use client";

import { useQueryClient } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import { useTheme } from "next-themes";
import { useState } from "react";
import { toast } from "sonner";
import { ME_KEY, useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { Field } from "@/components/ui/field";
import { SelectField, SwitchRow } from "@/components/ui/form";
import { ShieldIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { SectionCard } from "@/components/ui/section-card";
import { StatusPill } from "@/components/ui/status-pill";
import { errorMessage, mutate } from "@/services/api/client";
import type { Me, Preferences, SwipeAction } from "@/services/api/types";

const ZONES = ["Africa/Dar_es_Salaam", "Africa/Nairobi", "Africa/Kampala", "Africa/Kigali", "Africa/Johannesburg", "Africa/Lagos", "Europe/London", "UTC"];
const SWIPES: { value: SwipeAction; label: string }[] = [{ value: "archive", label: "Archive" }, { value: "trash", label: "Delete" }, { value: "read", label: "Mark read / unread" }, { value: "none", label: "Nothing" }];

export default function PreferencesPage() {
  usePageTitle({ page: "Preferences", section: "Settings" });
  const { me, preferences, updatePreferences } = useSession();
  const { theme, setTheme } = useTheme();

  const update = async (patch: Partial<Preferences> & { timezone?: string }) => {
    try { await updatePreferences(patch); toast.success("Preference saved.", { id: "pref" }); }
    catch (e) { toast.error(errorMessage(e)); }
  };
  const zones = me && !ZONES.includes(me.user.timezone) ? [me.user.timezone, ...ZONES] : ZONES;

  return (
    <Page className="max-w-3xl">
      <PageHeader title="Preferences" description="Personal settings. They follow you on every device." />
      <div className="space-y-4 sm:space-y-5">
        <SectionCard title="Appearance and time">
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField label="Theme" value={theme ?? "light"} onChange={(e) => setTheme(e.target.value)} options={[{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }, { value: "system", label: "Same as device" }]} />
            <SelectField label="Time zone" value={me?.user.timezone ?? "Africa/Dar_es_Salaam"} onChange={(e) => update({ timezone: e.target.value })} options={zones.map((z) => ({ value: z, label: z.replace(/_/g, " ") }))} hint="Dates and times everywhere use this zone." />
          </div>
        </SectionCard>

        <SectionCard title="Mail">
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField label="List density" value={preferences.density} onChange={(e) => update({ density: e.target.value as Preferences["density"] })} options={[{ value: "comfortable", label: "Comfortable" }, { value: "compact", label: "Compact" }]} />
            <SelectField label="Reading pane" value={preferences.reading_pane} onChange={(e) => update({ reading_pane: e.target.value as Preferences["reading_pane"] })} options={[{ value: "right", label: "Right of the list (desktop)" }, { value: "none", label: "No split: open full page" }]} />
            <SelectField label="Undo send" value={String(preferences.undo_send_seconds)} onChange={(e) => update({ undo_send_seconds: Number(e.target.value) as Preferences["undo_send_seconds"] })}
              options={[0, 5, 10, 20, 30].map((s) => ({ value: String(s), label: s ? `${s} seconds` : "Off: send immediately" }))} />
            <div />
            <SelectField label="Swipe right on a message (phones)" value={preferences.swipe_right} onChange={(e) => update({ swipe_right: e.target.value as SwipeAction })} options={SWIPES} />
            <SelectField label="Swipe left on a message (phones)" value={preferences.swipe_left} onChange={(e) => update({ swipe_left: e.target.value as SwipeAction })} options={SWIPES} />
          </div>
          <div className="mt-2 border-t border-card-border">
            <SwitchRow title="Keyboard shortcuts" description="Gmail-style keys: c compose, / search, j/k move, e archive, # delete… Press ? to see them all." checked={preferences.shortcuts} onChange={(shortcuts) => update({ shortcuts })} />
          </div>
        </SectionCard>

        <TwoFactor />
      </div>
    </Page>
  );
}

function TwoFactor() {
  const { me } = useSession();
  const client = useQueryClient();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string; qr_svg: string } | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [disabling, setDisabling] = useState(false);
  const enabled = !!me?.user.totp_enabled;

  const run = async (fn: () => Promise<unknown>) => { setBusy(true); try { await fn(); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); } };

  return (
    <SectionCard title={<span className="flex items-center gap-2"><ShieldIcon size={18} />Two-step sign-in</span>}
      description="Ask for a 6-digit code from an authenticator app when you sign in. Recommended for admins."
      actions={enabled ? <StatusPill tone="success">On</StatusPill> : <StatusPill tone="neutral">Off</StatusPill>}>
      {!enabled && !setup && <Button appearance="outline" isPending={busy} onPress={() => run(async () => setSetup(await mutate("auth/totp/setup/", "POST")))}>Set up</Button>}
      {!enabled && setup && (
        <div className="flex flex-col gap-5 sm:flex-row">
          <div className="shrink-0 self-start rounded-xl border border-card-border bg-white p-2 [&_svg]:size-40" role="img" aria-label="QR code for your authenticator app"
            dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(setup.qr_svg, { USE_PROFILES: { svg: true } }) }} />
          <div className="min-w-0 flex-1 space-y-3 text-sm">
            <p>Scan the code with Google Authenticator, Microsoft Authenticator or similar. Or enter this key: <code className="break-all rounded bg-background-gray-secondary_alt px-1.5 py-0.5">{setup.secret}</code></p>
            <Field label="6-digit code" value={code} onChange={setCode} inputMode="numeric" autoComplete="one-time-code" />
            <Button isPending={busy} isDisabled={code.length < 6} onPress={() => run(async () => {
              client.setQueryData<Me>(ME_KEY, await mutate("auth/totp/enable/", "POST", { code }));
              setSetup(null); setCode(""); toast.success("Two-step sign-in is on.");
            })}>Turn on</Button>
          </div>
        </div>
      )}
      {enabled && !disabling && <Button variant="danger" appearance="outline" onPress={() => setDisabling(true)}>Turn off</Button>}
      {enabled && disabling && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="w-48"><Field label="Current 6-digit code" value={code} onChange={setCode} inputMode="numeric" autoComplete="one-time-code" /></div>
          <Button variant="danger" isPending={busy} isDisabled={code.length < 6} onPress={() => run(async () => {
            client.setQueryData<Me>(ME_KEY, await mutate("auth/totp/disable/", "POST", { code }));
            setDisabling(false); setCode(""); toast("Two-step sign-in is off.");
          })}>Confirm</Button>
          <Button appearance="ghost" onPress={() => setDisabling(false)}>Cancel</Button>
        </div>
      )}
    </SectionCard>
  );
}

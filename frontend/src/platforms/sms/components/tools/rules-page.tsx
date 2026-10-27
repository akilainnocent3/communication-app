"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { Field } from "@/components/ui/field";
import { SelectField, SwitchRow } from "@/components/ui/form";
import { PlusIcon, TrashIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage, fieldError, mutate } from "@/services/api/client";
import type { SensitiveRule } from "@/services/api/types";
import { smsKeys } from "../../api/keys";
import { useRules } from "../../api/queries";

const BUILT_IN = [
  "One-time codes: “verification code”, “OTP”, “msimbo”, “G-123456”, “123-456”…",
  "Mobile money and banks: M-PESA, Tigo Pesa, Airtel Money, HaloPesa, CRDB, NMB, NBC… and “salio / balance … TSh” texts",
];

/** Patterns that make a message sensitive: masked in the admin, revealed only with permission, and audited. */
export function RulesPage() {
  usePageTitle({ page: "Sensitive-message rules", section: "Tools" });
  const { can } = useSession();
  const rules = useRules();
  const client = useQueryClient();
  const [draft, setDraft] = useState<{ name: string; kind: "otp" | "money"; sender_pattern: string; body_pattern: string } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const canEdit = can("sms.manage_devices");
  const refresh = () => client.invalidateQueries({ queryKey: smsKeys.rules() });
  const create = async () => {
    setError(null);
    try { await mutate("sms/rules/", "POST", { ...draft, is_enabled: true }); setDraft(null); refresh(); toast.success("Rule added. It applies to new messages."); }
    catch (e) { setError(e); }
  };
  return (
    <Page>
      <PageHeader title="Sensitive-message rules" description="Messages that match are masked (“Verification code ••••••”). Revealing one needs the “Reveal codes” permission and is written to the audit log."
        actions={canEdit && !draft && <Button onPress={() => setDraft({ name: "", kind: "otp", sender_pattern: "", body_pattern: "" })}><PlusIcon size={16} />Add rule</Button>} />
      <SectionCard className="mb-4" title="Built in" description="Always on.">
        <ul className="list-disc space-y-1 pl-5 text-sm text-text-secondary">{BUILT_IN.map((line) => <li key={line}>{line}</li>)}</ul>
      </SectionCard>
      {draft && (
        <SectionCard className="mb-4" title="New rule" footer={<div className="flex justify-end gap-2"><Button appearance="outline" onPress={() => setDraft(null)}>Cancel</Button><Button onPress={create} isDisabled={!draft.name.trim()}>Add rule</Button></div>}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" value={draft.name} onChange={(name) => setDraft({ ...draft, name })} autoFocus error={fieldError(error, "name")} />
            <SelectField label="Kind" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as "otp" | "money" })} options={[{ value: "otp", label: "One-time code" }, { value: "money", label: "Banking / mobile money" }]} />
            <Field label="Sender pattern (regular expression)" value={draft.sender_pattern} onChange={(sender_pattern) => setDraft({ ...draft, sender_pattern })} placeholder="(?i)^payroll" error={fieldError(error, "sender_pattern")} />
            <Field label="Text pattern (regular expression)" value={draft.body_pattern} onChange={(body_pattern) => setDraft({ ...draft, body_pattern })} placeholder="(?i)salary slip" error={fieldError(error, "body_pattern")} />
          </div>
          {!!error && !fieldError(error, "name") && !fieldError(error, "sender_pattern") && !fieldError(error, "body_pattern") && <p role="alert" className="mt-3 text-sm text-error-500">{errorMessage(error)}</p>}
        </SectionCard>
      )}
      <SectionCard title="Your rules">
        {rules.isPending || rules.error ? <RequestState loading={rules.isPending} error={errorMessage(rules.error)} onRetry={() => rules.refetch()} /> : rules.data!.length === 0 ? <p className="text-sm text-text-tertiary">No extra rules.</p> : (
          <ul className="divide-y divide-card-border">{rules.data!.map((rule) => <RuleRow key={rule.id} rule={rule} canEdit={canEdit} onChange={refresh} />)}</ul>
        )}
      </SectionCard>
    </Page>
  );
}

function RuleRow({ rule, canEdit, onChange }: { rule: SensitiveRule; canEdit: boolean; onChange: () => void }) {
  return (
    <li className="flex items-start gap-3 py-2">
      <div className="min-w-0 flex-1">
        <SwitchRow title={`${rule.name} · ${rule.kind === "otp" ? "One-time code" : "Money"}`} description={[rule.sender_pattern && `sender ${rule.sender_pattern}`, rule.body_pattern && `text ${rule.body_pattern}`].filter(Boolean).join(" · ")}
          checked={rule.is_enabled ?? true} disabled={!canEdit} onChange={async (value) => { try { await mutate(`sms/rules/${rule.id}/`, "PATCH", { is_enabled: value }); onChange(); } catch (e) { toast.error(errorMessage(e)); } }} />
      </div>
      {canEdit && <Button size="sm" appearance="ghost" iconOnly aria-label={`Delete ${rule.name}`} className="mt-3" onPress={async () => { try { await mutate(`sms/rules/${rule.id}/`, "DELETE"); onChange(); } catch (e) { toast.error(errorMessage(e)); } }}><TrashIcon size={16} /></Button>}
    </li>
  );
}

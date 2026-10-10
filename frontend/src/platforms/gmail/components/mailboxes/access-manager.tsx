"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { TrashIcon } from "@/components/ui/icons";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage, mutate, request } from "@/services/api/client";
import type { AccessEntry, User } from "@/services/api/types";
import { mailKeys } from "../../api/keys";

const PERMS = [
  { key: "can_read", label: "Read" },
  { key: "can_send", label: "Send" },
  { key: "can_delete", label: "Delete" },
  { key: "can_manage", label: "Manage" },
] as const;
type Entry = Pick<AccessEntry, "user" | "email" | "display_name" | "can_read" | "can_send" | "can_delete" | "can_manage">;

/** Per-mailbox access for office managers and viewers (admins already see every mailbox). */
export function AccessManager({ mailboxId }: { mailboxId: number }) {
  const { can } = useSession();
  const client = useQueryClient();
  const access = useQuery({ queryKey: mailKeys.access(mailboxId), queryFn: () => request<AccessEntry[]>(`mail/mailboxes/${mailboxId}/access/`) });
  const canListUsers = can("identity.manage_users");
  const users = useQuery({ queryKey: ["settings", "users"], queryFn: () => request<User[]>("settings/users/"), enabled: canListUsers, staleTime: 60_000 });
  // null = unchanged (show the server's list); a copy is made on the first edit.
  const [edited, setRows] = useState<Entry[] | null>(null);
  const rows: Entry[] | null = edited ?? access.data ?? null;
  const [adding, setAdding] = useState("");
  const [saving, setSaving] = useState(false);

  const dirty = useMemo(() => edited !== null && JSON.stringify(edited) !== JSON.stringify(access.data), [edited, access.data]);
  const candidates = (users.data ?? []).filter((user) => user.is_active !== false && !rows?.some((row) => row.user === user.id));

  const set = (user: number, key: (typeof PERMS)[number]["key"], value: boolean) =>
    setRows(() => rows?.map((row) => {
      if (row.user !== user) return row;
      const next = { ...row, [key]: value };
      if (key !== "can_read" && value) next.can_read = true; // every other right implies reading
      if (key === "can_read" && !value) Object.assign(next, { can_send: false, can_delete: false, can_manage: false });
      return next;
    }) ?? null);

  const save = async () => {
    if (!rows) return;
    setSaving(true);
    try {
      const data = await mutate<AccessEntry[]>(`mail/mailboxes/${mailboxId}/access/`, "PUT", rows.map(({ user, can_read, can_send, can_delete, can_manage }) => ({ user, can_read, can_send, can_delete, can_manage })));
      client.setQueryData(mailKeys.access(mailboxId), data);
      setRows(null);
      toast.success("Access updated.");
    } catch (error) { toast.error(errorMessage(error)); } finally { setSaving(false); }
  };

  return (
    <SectionCard title="Who can use this mailbox" description="Admins can open every mailbox. Give office managers and viewers access here."
      footer={dirty && <div className="flex justify-end gap-2"><Button appearance="outline" onPress={() => setRows(null)}>Discard</Button><Button onPress={save} isPending={saving}>Save access</Button></div>}>
      {access.isPending || access.error ? <RequestState loading={access.isPending} error={errorMessage(access.error)} onRetry={() => access.refetch()} /> : (
        <>
          {rows && rows.length > 0 ? (
            <div className="-mx-1 overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead className="text-left text-xs text-text-tertiary">
                  <tr><th className="px-1 py-2 font-medium">Person</th>{PERMS.map((p) => <th key={p.key} className="px-1 py-2 text-center font-medium">{p.label}</th>)}<th className="w-10" /></tr>
                </thead>
                <tbody className="divide-y divide-card-border">
                  {rows.map((row) => (
                    <tr key={row.user}>
                      <td className="px-1 py-2.5"><p className="font-medium text-text-primary">{row.display_name}</p><p className="text-xs text-text-tertiary">{row.email}</p></td>
                      {PERMS.map((p) => (
                        <td key={p.key} className="px-1 py-2.5 text-center">
                          <input type="checkbox" checked={!!row[p.key]} onChange={(e) => set(row.user, p.key, e.target.checked)} aria-label={`${p.label} for ${row.display_name}`}
                            className="size-4 rounded border-card-border text-primary-500 focus:ring-primary-500" />
                        </td>
                      ))}
                      <td className="text-right">
                        <Button size="sm" appearance="ghost" iconOnly aria-label={`Remove ${row.display_name}`} onPress={() => setRows(rows.filter((r) => r.user !== row.user))}><TrashIcon size={16} /></Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="py-4 text-sm text-text-tertiary">Only admins can open this mailbox right now.</p>}
          {canListUsers && candidates.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              <label className="sr-only" htmlFor={`add-access-${mailboxId}`}>Add a person</label>
              <select id={`add-access-${mailboxId}`} value={adding} onChange={(e) => setAdding(e.target.value)}
                className="h-9 min-w-0 flex-1 rounded-lg border border-card-border bg-input-background px-3 text-sm text-text-primary sm:max-w-xs">
                <option value="">Add a person…</option>
                {candidates.map((user) => <option key={user.id} value={user.id}>{user.display_name} ({user.email})</option>)}
              </select>
              <Button size="sm" appearance="outline" isDisabled={!adding} onPress={() => {
                const user = candidates.find((u) => u.id === Number(adding));
                if (!user) return;
                setRows([...(rows ?? []), { user: user.id, email: user.email, display_name: user.display_name, can_read: true, can_send: false, can_delete: false, can_manage: false }]);
                setAdding("");
              }}>Add</Button>
            </div>
          )}
        </>
      )}
    </SectionCard>
  );
}

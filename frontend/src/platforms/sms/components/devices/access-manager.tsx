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
import type { DeviceAccessEntry, User } from "@/services/api/types";
import { smsKeys } from "../../api/keys";

const PERMS = [
  { key: "can_read", label: "Read" },
  { key: "can_send", label: "Send" },
  { key: "can_manage", label: "Manage" },
  { key: "can_reveal_sensitive", label: "Reveal codes" },
] as const;
type Entry = Pick<DeviceAccessEntry, "user" | "email" | "display_name" | "can_read" | "can_send" | "can_manage" | "can_reveal_sensitive">;

/** Per-phone access for office managers and viewers (admins already open every phone). Mirrors the mailbox access manager. */
export function DeviceAccessManager({ deviceId }: { deviceId: string }) {
  const { can } = useSession();
  const client = useQueryClient();
  const access = useQuery({ queryKey: smsKeys.access(deviceId), queryFn: () => request<DeviceAccessEntry[]>(`sms/devices/${deviceId}/access/`) });
  const canListUsers = can("identity.manage_users");
  const users = useQuery({ queryKey: ["settings", "users"], queryFn: () => request<User[]>("settings/users/"), enabled: canListUsers, staleTime: 60_000 });
  const [edited, setRows] = useState<Entry[] | null>(null);
  const rows: Entry[] | null = edited ?? access.data ?? null;
  const [adding, setAdding] = useState("");
  const [saving, setSaving] = useState(false);
  const dirty = useMemo(() => edited !== null && JSON.stringify(edited) !== JSON.stringify(access.data), [edited, access.data]);
  const candidates = (users.data ?? []).filter((user) => user.is_active !== false && !rows?.some((row) => row.user === user.id));

  const set = (user: number, key: (typeof PERMS)[number]["key"], value: boolean) =>
    setRows(rows?.map((row) => {
      if (row.user !== user) return row;
      const next = { ...row, [key]: value };
      if (key !== "can_read" && value) next.can_read = true;
      if (key === "can_read" && !value) Object.assign(next, { can_send: false, can_manage: false, can_reveal_sensitive: false });
      return next;
    }) ?? null);

  const save = async () => {
    if (!rows) return;
    setSaving(true);
    try {
      const data = await mutate<DeviceAccessEntry[]>(`sms/devices/${deviceId}/access/`, "PUT", rows.map(({ user, can_read, can_send, can_manage, can_reveal_sensitive }) => ({ user, can_read, can_send, can_manage, can_reveal_sensitive })));
      client.setQueryData(smsKeys.access(deviceId), data);
      setRows(null);
      toast.success("Access updated.");
    } catch (error) { toast.error(errorMessage(error)); } finally { setSaving(false); }
  };

  return (
    <SectionCard title="Who can use this phone" description="Admins open every phone. Give office managers and viewers access here. “Reveal codes” shows one-time codes and money messages, and every reveal is logged."
      footer={dirty && <div className="flex justify-end gap-2"><Button appearance="outline" onPress={() => setRows(null)}>Discard</Button><Button onPress={save} isPending={saving}>Save access</Button></div>}>
      {access.isPending || access.error ? <RequestState loading={access.isPending} error={errorMessage(access.error)} onRetry={() => access.refetch()} /> : (
        <>
          {rows && rows.length > 0 ? (
            <div className="-mx-1 overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="text-left text-xs text-text-tertiary"><tr><th className="px-1 py-2 font-medium">Person</th>{PERMS.map((p) => <th key={p.key} className="px-1 py-2 text-center font-medium">{p.label}</th>)}<th className="w-10" /></tr></thead>
                <tbody className="divide-y divide-card-border">
                  {rows.map((row) => (
                    <tr key={row.user}>
                      <td className="px-1 py-2.5"><p className="font-medium text-text-primary">{row.display_name}</p><p className="text-xs text-text-tertiary">{row.email}</p></td>
                      {PERMS.map((p) => (
                        <td key={p.key} className="px-1 py-2.5 text-center">
                          <input type="checkbox" checked={!!row[p.key]} onChange={(e) => set(row.user, p.key, e.target.checked)} aria-label={`${p.label} for ${row.display_name}`} className="size-4 rounded border-card-border text-primary-500 focus:ring-primary-500" />
                        </td>
                      ))}
                      <td className="text-right"><Button size="sm" appearance="ghost" iconOnly aria-label={`Remove ${row.display_name}`} onPress={() => setRows(rows.filter((r) => r.user !== row.user))}><TrashIcon size={16} /></Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="py-4 text-sm text-text-tertiary">Only admins can open this phone right now.</p>}
          {canListUsers && candidates.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              <label className="sr-only" htmlFor={`add-device-access-${deviceId}`}>Add a person</label>
              <select id={`add-device-access-${deviceId}`} value={adding} onChange={(e) => setAdding(e.target.value)} className="h-9 min-w-0 flex-1 rounded-lg border border-card-border bg-input-background px-3 text-sm text-text-primary sm:max-w-xs">
                <option value="">Add a person…</option>
                {candidates.map((user) => <option key={user.id} value={user.id}>{user.display_name} ({user.email})</option>)}
              </select>
              <Button size="sm" appearance="outline" isDisabled={!adding} onPress={() => {
                const user = candidates.find((u) => u.id === Number(adding));
                if (!user) return;
                setRows([...(rows ?? []), { user: user.id, email: user.email, display_name: user.display_name, can_read: true, can_send: false, can_manage: false, can_reveal_sensitive: false }]);
                setAdding("");
              }}>Add</Button>
            </div>
          )}
        </>
      )}
    </SectionCard>
  );
}

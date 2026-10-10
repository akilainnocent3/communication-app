"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Form } from "react-aria-components";
import { toast } from "sonner";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field } from "@/components/ui/field";
import { SelectField, SwitchRow } from "@/components/ui/form";
import { PencilIcon, PlusIcon, SearchIcon, TrashIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { Chip, StatusPill } from "@/components/ui/status-pill";
import { ago } from "@/lib/format";
import { errorMessage, fieldError, mutate, request } from "@/services/api/client";
import type { Office, PermissionItem, Role, User } from "@/services/api/types";
import { cn } from "@/utils/cn";

const USERS = ["settings", "users"] as const;
const ROLES = ["settings", "roles"] as const;

export default function UsersPage() {
  usePageTitle({ page: "Users & roles", section: "Settings" });
  const { can } = useSession();
  const [tab, setTab] = useState<"users" | "roles">("users");
  if (!can("identity.manage_users")) return <Page><PageHeader title="Users & roles" description="You don't have permission to manage users." /></Page>;
  return (
    <Page wide>
      <PageHeader title="Users & roles" description="Who can sign in, and what each role is allowed to do." />
      <div role="tablist" aria-label="Users and roles" className="mb-4 inline-flex rounded-lg border border-card-border bg-card-surface-area p-0.5">
        {(["users", "roles"] as const).map((key) => (
          <button key={key} role="tab" type="button" aria-selected={tab === key} onClick={() => setTab(key)}
            className={cn("h-8 rounded-md px-4 text-sm font-medium capitalize transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none", tab === key ? "bg-primary-500 text-white" : "text-text-secondary hover:text-text-primary")}>{key}</button>
        ))}
      </div>
      {tab === "users" ? <UsersTab /> : <RolesTab />}
    </Page>
  );
}

function UsersTab() {
  const { me } = useSession();
  const users = useQuery({ queryKey: USERS, queryFn: () => request<User[]>("settings/users/") });
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<User | "new" | null>(null);
  const items = (users.data ?? []).filter((u) => !q || `${u.email} ${u.full_name}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="relative block w-full max-w-sm">
          <span className="sr-only">Search users</span>
          <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-icon-tertiary" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or email" className="h-10 w-full rounded-lg border border-card-border bg-input-background pr-3 pl-9 text-sm text-text-primary outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20" />
        </label>
        <Button onPress={() => setEditing("new")}><PlusIcon size={16} />Add user</Button>
      </div>
      {users.isPending || users.error ? <RequestState variant="table" loading={users.isPending} error={errorMessage(users.error)} onRetry={() => users.refetch()} /> : (
        <div className="overflow-x-auto rounded-xl border border-card-border bg-card-surface-area">
          <table className="w-full min-w-[680px] text-sm">
            <thead className="border-b border-card-border bg-background-gray-secondary_alt/40 text-left text-xs text-text-tertiary">
              <tr><th className="px-4 py-2.5 font-medium">Name</th><th className="px-4 py-2.5 font-medium">Role</th><th className="px-4 py-2.5 font-medium">Office</th><th className="px-4 py-2.5 font-medium">Status</th><th className="px-4 py-2.5 font-medium">Last sign-in</th><th className="w-12" /></tr>
            </thead>
            <tbody className="divide-y divide-card-border">
              {items.map((user) => (
                <tr key={user.id} className="hover:bg-background-gray-secondary_alt/30">
                  <td className="px-4 py-3"><p className="font-medium text-text-primary">{user.display_name}{user.id === me?.user.id && <span className="ml-1.5 text-xs font-normal text-text-tertiary">(you)</span>}</p><p className="text-xs text-text-tertiary">{user.email}</p></td>
                  <td className="px-4 py-3">{user.role ? <Chip>{String(user.role.name)}</Chip> : <span className="text-text-tertiary">—</span>}</td>
                  <td className="px-4 py-3 text-text-secondary">{user.office?.name ?? "—"}</td>
                  <td className="px-4 py-3">{user.is_active === false ? <StatusPill tone="neutral">Inactive</StatusPill> : <StatusPill tone="success">Active</StatusPill>}{user.totp_enabled && <Chip className="ml-1.5">2-step</Chip>}</td>
                  <td className="px-4 py-3 text-text-secondary">{user.last_login ? ago(user.last_login) : "Never"}</td>
                  <td className="px-2 text-right"><Button size="sm" appearance="ghost" iconOnly aria-label={`Edit ${user.display_name}`} onPress={() => setEditing(user)}><PencilIcon size={16} /></Button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && <p className="py-10 text-center text-sm text-text-tertiary">No users match.</p>}
        </div>
      )}
      {editing && <UserDialog user={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function UserDialog({ user, onClose }: { user: User | null; onClose: () => void }) {
  const client = useQueryClient();
  const roles = useQuery({ queryKey: ROLES, queryFn: () => request<Role[]>("settings/roles/") });
  const offices = useQuery({ queryKey: ["settings", "offices"], queryFn: () => request<Office[]>("settings/offices/") });
  const [values, setValues] = useState({
    email: user?.email ?? "", full_name: user?.full_name ?? "", role: (user?.role?.slug as string | undefined) ?? "viewer",
    office: user?.office ? String(user.office.id) : "", is_active: user?.is_active !== false, password: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const set = (patch: Partial<typeof values>) => setValues((v) => ({ ...v, ...patch }));

  const submit = async () => {
    setBusy(true); setError(null);
    const payload = { ...values, role: values.role || null, office: values.office ? Number(values.office) : null, password: values.password || undefined };
    try {
      if (user) await mutate(`settings/users/${user.id}/`, "PATCH", payload); else await mutate("settings/users/", "POST", payload);
      client.invalidateQueries({ queryKey: USERS }); client.invalidateQueries({ queryKey: ROLES });
      toast.success(user ? "User updated." : `${values.email} can now sign in.`);
      onClose();
    } catch (e) { setError(e); } finally { setBusy(false); }
  };

  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} className="max-w-lg">
      <DialogHeader><DialogTitle>{user ? `Edit ${user.display_name}` : "Add user"}</DialogTitle></DialogHeader>
      <Form className="mt-4 space-y-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <Field label="Full name" value={values.full_name} onChange={(full_name) => set({ full_name })} autoFocus error={fieldError(error, "full_name")} />
        <Field label="Email" type="email" value={values.email} onChange={(email) => set({ email })} isRequired error={fieldError(error, "email")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label="Role" value={values.role} onChange={(e) => set({ role: e.target.value })} options={(roles.data ?? []).map((r) => ({ value: r.slug, label: r.name }))} error={fieldError(error, "role")} />
          <SelectField label="Office" value={values.office} onChange={(e) => set({ office: e.target.value })} options={[{ value: "", label: "No office" }, ...(offices.data ?? []).map((o) => ({ value: String(o.id), label: o.name }))]} />
        </div>
        <Field label={user ? "New password (leave empty to keep)" : "Password"} type="password" autoComplete="new-password" value={values.password} onChange={(password) => set({ password })}
          isRequired={!user} error={fieldError(error, "password")} hint="At least 10 characters. Share it privately; they can change it later." />
        {user && <SwitchRow title="Active" description="Inactive users cannot sign in." checked={values.is_active} onChange={(is_active) => set({ is_active })} />}
        {!!error && !["email", "password", "role", "full_name"].some((f) => fieldError(error, f)) && <p role="alert" className="text-sm text-error-500">{errorMessage(error)}</p>}
        <div className="flex justify-end gap-2 pt-2"><Button appearance="outline" onPress={onClose}>Cancel</Button><Button type="submit" isPending={busy}>{user ? "Save" : "Add user"}</Button></div>
      </Form>
    </Dialog>
  );
}

function RolesTab() {
  const client = useQueryClient();
  const roles = useQuery({ queryKey: ROLES, queryFn: () => request<Role[]>("settings/roles/") });
  const catalog = useQuery({ queryKey: ["settings", "permissions"], queryFn: () => request<PermissionItem[]>("settings/permissions/"), staleTime: Infinity });
  const [editing, setEditing] = useState<Role | "new" | null>(null);
  const [deleting, setDeleting] = useState<Role | null>(null);
  const name = (code: string) => catalog.data?.find((p) => p.code === code)?.name ?? code;

  return (
    <>
      <div className="mb-4 flex justify-end"><Button onPress={() => setEditing("new")}><PlusIcon size={16} />New role</Button></div>
      {roles.isPending || roles.error ? <RequestState variant="table" loading={roles.isPending} error={errorMessage(roles.error)} onRetry={() => roles.refetch()} /> : (
        <ul className="grid gap-3 md:grid-cols-2">
          {roles.data!.map((role) => (
            <li key={role.id} className="rounded-xl border border-card-border bg-card-surface-area p-4">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 font-semibold text-text-primary">{role.name}{role.is_system && <Chip>Built-in</Chip>}</p>
                  <p className="mt-0.5 text-sm text-text-tertiary">{role.description || "No description"}</p>
                </div>
                <span className="text-xs text-text-tertiary tabular-nums">{role.user_count} {role.user_count === 1 ? "user" : "users"}</span>
              </div>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {role.slug === "super_admin" ? <li><Chip>Everything</Chip></li> : role.permissions.length ? role.permissions.map((code) => <li key={code}><Chip title={code}>{name(code)}</Chip></li>) : <li className="text-xs text-text-tertiary">No permissions</li>}
              </ul>
              {role.slug !== "super_admin" && (
                <div className="mt-3 flex gap-1 border-t border-card-border pt-2">
                  <Button size="sm" appearance="ghost" onPress={() => setEditing(role)}><PencilIcon size={15} />Edit</Button>
                  {!role.is_system && <Button size="sm" appearance="ghost" variant="danger" onPress={() => setDeleting(role)}><TrashIcon size={15} />Delete</Button>}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {editing && <RoleDialog role={editing === "new" ? null : editing} catalog={catalog.data ?? []} onClose={() => setEditing(null)} />}
      <ConfirmDialog isOpen={!!deleting} onOpenChange={(o) => !o && setDeleting(null)} title={`Delete the role “${deleting?.name}”?`} confirmLabel="Delete role" body="Only roles with no users can be deleted."
        onConfirm={async () => {
          if (!deleting) return;
          try { await mutate(`settings/roles/${deleting.id}/`, "DELETE"); client.invalidateQueries({ queryKey: ROLES }); toast("Role deleted."); }
          catch (e) { toast.error(errorMessage(e)); throw e; }
        }} />
    </>
  );
}

function RoleDialog({ role, catalog, onClose }: { role: Role | null; catalog: PermissionItem[]; onClose: () => void }) {
  const client = useQueryClient();
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [perms, setPerms] = useState<Set<string>>(new Set(role?.permissions ?? ["mail.access"]));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const submit = async () => {
    setBusy(true); setError(null);
    const payload = { name, description, permissions: [...perms] };
    try {
      if (role) await mutate(`settings/roles/${role.id}/`, "PATCH", payload); else await mutate("settings/roles/", "POST", payload);
      client.invalidateQueries({ queryKey: ROLES }); toast.success("Role saved."); onClose();
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  return (
    <Dialog isOpen onOpenChange={(o) => !o && onClose()} className="max-w-lg">
      <DialogHeader><DialogTitle>{role ? `Edit ${role.name}` : "New role"}</DialogTitle></DialogHeader>
      <Form className="mt-4 space-y-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <Field label="Name" value={name} onChange={setName} isRequired autoFocus error={fieldError(error, "name")} />
        <Field label="Description" value={description} onChange={setDescription} />
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Permissions</legend>
          <div className="space-y-2">
            {catalog.map((p) => (
              <label key={p.code} className="flex items-start gap-2 text-sm">
                <input type="checkbox" checked={perms.has(p.code)} className="mt-0.5 size-4 rounded border-card-border text-primary-500"
                  onChange={(e) => setPerms((s) => { const n = new Set(s); if (e.target.checked) n.add(p.code); else n.delete(p.code); return n; })} />
                <span><span className="text-text-primary">{p.name}</span> <code className="text-xs text-text-tertiary">{p.code}</code></span>
              </label>
            ))}
          </div>
        </fieldset>
        {!!error && !fieldError(error, "name") && <p role="alert" className="text-sm text-error-500">{errorMessage(error)}</p>}
        <div className="flex justify-end gap-2 pt-2"><Button appearance="outline" onPress={onClose}>Cancel</Button><Button type="submit" isPending={busy}>Save role</Button></div>
      </Form>
    </Dialog>
  );
}

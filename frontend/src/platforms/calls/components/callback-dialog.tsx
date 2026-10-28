"use client";

import { useState } from "react";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogBody, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { m } from "@/i18n";
import { useCreateCallback } from "../api/actions";
import { useCallsDevices } from "../api/queries";

const FIELD = "h-10 w-full rounded-lg border border-card-border bg-card-surface-area px-3 text-sm text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none";

export type CallbackSeed = { device?: string; number?: string; call?: number; customer?: number; title?: string };

/** Ask a phone's holder to call a customer back. Only phones where the user may assign call-backs are offered. */
export function CallbackDialog({ seed, onClose }: { seed: CallbackSeed | null; onClose: () => void }) {
  const devices = useCallsDevices().filter((device) => device.permissions.assign && device.status === "active");
  const create = useCreateCallback();
  const [device, setDevice] = useState(seed?.device ?? "");
  const [number, setNumber] = useState(seed?.number ?? "");
  const [priority, setPriority] = useState("normal");
  const [reason, setReason] = useState("");
  const [due, setDue] = useState("");
  const chosen = device || (devices.length === 1 ? devices[0].id : "");
  return (
    <Dialog isOpen={!!seed} onOpenChange={(open) => !open && onClose()} className="max-w-lg" aria-label={m.calls.createCallback}>
      <DialogHeader><DialogTitle>{m.calls.createCallback}{seed?.title ? `: ${seed.title}` : ""}</DialogTitle><DialogDescription>{m.calls.callbackHelp}</DialogDescription></DialogHeader>
      <DialogBody>
        <form id="callback-form" className="grid gap-3" onSubmit={(event) => {
          event.preventDefault();
          create.mutate({ device: chosen, number: seed?.call ? undefined : number, call: seed?.call ?? null, customer: seed?.customer ?? null, priority, reason,
            due_at: due ? new Date(due).toISOString() : null }, { onSuccess: onClose });
        }}>
          <label className="grid gap-1 text-sm"><span className="font-medium text-text-primary">Phone that calls back</span>
            <select required value={chosen} onChange={(e) => setDevice(e.target.value)} className={FIELD} aria-label="Phone that calls back">
              <option value="" disabled>Choose a phone</option>
              {devices.map((d) => <option key={d.id} value={d.id}>{d.name} · {d.office.name}</option>)}
            </select>
          </label>
          {!seed?.call && (
            <label className="grid gap-1 text-sm"><span className="font-medium text-text-primary">Number</span>
              <input required inputMode="tel" value={number} onChange={(e) => setNumber(e.target.value)} placeholder="0754 210 331" className={FIELD} />
            </label>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm"><span className="font-medium text-text-primary">Priority</span>
              <select value={priority} onChange={(e) => setPriority(e.target.value)} className={FIELD}>
                {Object.entries(m.calls.priority).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-sm"><span className="font-medium text-text-primary">Due <span className="font-normal text-text-tertiary">(optional)</span></span>
              <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} className={FIELD} />
            </label>
          </div>
          <label className="grid gap-1 text-sm"><span className="font-medium text-text-primary">Reason <span className="font-normal text-text-tertiary">(shown on the phone)</span></span>
            <textarea value={reason} maxLength={500} rows={3} onChange={(e) => setReason(e.target.value)} placeholder="Asked about the cement order"
              className="w-full rounded-lg border border-card-border bg-card-surface-area px-3 py-2 text-sm text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none" />
          </label>
          {devices.length === 0 && <p className="text-sm text-warning-600">You can&apos;t assign call-backs on any phone.</p>}
        </form>
      </DialogBody>
      <DialogFooter>
        <Button appearance="outline" onPress={onClose}>{m.common.cancel}</Button>
        <Button type="submit" form="callback-form" isPending={create.isPending} isDisabled={!chosen}>Send to phone</Button>
      </DialogFooter>
    </Dialog>
  );
}

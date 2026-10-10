"use client";

import { useState, type ReactNode } from "react";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";

/** Confirmation for destructive actions; the confirm button shows progress and the dialog stays until it resolves. */
export function ConfirmDialog({ isOpen, onOpenChange, title, body, confirmLabel, onConfirm, tone = "danger" }: {
  isOpen: boolean; onOpenChange: (open: boolean) => void; title: string; body: ReactNode; confirmLabel: string;
  onConfirm: () => Promise<unknown> | unknown; tone?: "danger" | "primary";
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Dialog isOpen={isOpen} onOpenChange={(open) => !busy && onOpenChange(open)} role="alertdialog" className="max-w-md">
      <DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
      <div className="mt-2 text-sm text-text-secondary">{body}</div>
      <div className="mt-6 flex justify-end gap-2">
        <Button appearance="outline" onPress={() => onOpenChange(false)} isDisabled={busy}>Cancel</Button>
        <Button variant={tone} isPending={busy} autoFocus onPress={async () => {
          setBusy(true);
          try { await onConfirm(); onOpenChange(false); } finally { setBusy(false); }
        }}>{confirmLabel}</Button>
      </div>
    </Dialog>
  );
}

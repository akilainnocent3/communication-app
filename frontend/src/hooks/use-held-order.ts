"use client";

import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react";

const MOVE_HOLD_MS = 1500;
const RELEASE_HOLD_MS = 600;

/**
 * Keeps a polled list from re-ordering under the user's pointer. While the pointer moves over the list, is pressed,
 * or was released a moment ago, rows keep their on-screen positions: their data still updates in place, rows that
 * arrive are held back and rows that left stay where they were. When the pointer rests or leaves, the server's order
 * applies again. Without this a row could move between pointerdown and pointerup, and the tap would land on another
 * row or on none (the cause of the flaky SMS journey on mobile, docs/decisions.md 61).
 */
export function useHeldOrder<T extends { id: number | string }>(rows: T[]) {
  const [frozen, setFrozen] = useState<T[] | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const pressed = useRef(false);

  const display = frozen ? reconcile(frozen, rows) : rows;

  const release = useCallback(() => {
    window.clearTimeout(timer.current);
    setFrozen(null);
  }, []);

  const hold = useCallback((current: T[], ms: number) => {
    setFrozen((previous) => previous ?? current);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      if (!pressed.current) setFrozen(null);
    }, ms);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const handlers = {
    onPointerMove: (event: PointerEvent) => {
      if (event.pointerType === "mouse" || pressed.current) hold(display, MOVE_HOLD_MS);
    },
    onPointerDown: () => {
      pressed.current = true;
      hold(display, MOVE_HOLD_MS);
    },
    onPointerUp: () => {
      pressed.current = false;
      hold(display, RELEASE_HOLD_MS);
    },
    onPointerCancel: () => {
      pressed.current = false;
      hold(display, RELEASE_HOLD_MS);
    },
    onPointerLeave: () => {
      if (!pressed.current) release();
    },
  };

  return { rows: display, held: frozen !== null, handlers };
}

/**
 * The frozen order with each row's latest data; ids that are gone keep their last known row. Rows after the last
 * frozen one (the next page of an infinite list) are appended: they move nothing that is on screen.
 */
function reconcile<T extends { id: number | string }>(frozen: T[], latest: T[]): T[] {
  const byId = new Map(latest.map((row) => [row.id, row]));
  const kept = new Set(frozen.map((row) => row.id));
  let tail = -1;
  latest.forEach((row, index) => { if (kept.has(row.id)) tail = index; });
  return [...frozen.map((row) => byId.get(row.id) ?? row), ...latest.slice(tail + 1).filter((row) => !kept.has(row.id))];
}

"use client";

/**
 * Optimistic auto-save for a single preference document.
 *
 * A toggle that waits for a round-trip feels broken, so the local copy
 * moves immediately and the PATCH follows. If the server refuses, the
 * change is **rolled back to the value the server last confirmed**  not
 * to whatever was on screen a moment ago  and the error is surfaced.
 * Settings that silently fail are worse than settings that cannot move.
 *
 * Only the changed keys are sent. Every endpoint behind this is a strict
 * PATCH where absent means "leave alone", so a narrow payload is both
 * cheaper and safer than echoing the whole document back.
 *
 * Concurrent saves are sequenced by a request counter: a slow first
 * response can no longer overwrite a faster second one, which is exactly
 * what happens when someone flips three switches quickly.
 */

import { useCallback, useRef, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

export type SaveStatus = "idle" | "saving" | "saved" | "error";

export interface AutoSave<T> {
  /** The value to render  optimistic, so the UI never lags a click. */
  value: T;
  /** Merge a partial change, then persist it. */
  update: (patch: Partial<T>) => void;
  status: SaveStatus;
  /** Human-readable failure from the last rejected save, if any. */
  error: string | null;
}

export function useAutoSave<T extends object>(
  /** The server's copy, from the page's initial read. */
  initial: T,
  /** Endpoint that accepts a partial PATCH of `T`. */
  path: string,
): AutoSave<T> {
  const [value, setValue] = useState<T>(initial);
  const [status, setStatus] = useState<SaveStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  /** The last state the server acknowledged  the rollback target. */
  const committed = useRef<T>(initial);
  /** Monotonic id so a stale response cannot win a race. */
  const sequence = useRef(0);
  const settled = useRef(0);

  const update = useCallback(
    (patch: Partial<T>) => {
      const optimistic = { ...committed.current, ...value, ...patch };
      setValue(optimistic);
      setStatus("saving");
      setError(null);

      const ticket = ++sequence.current;

      void api
        .patch<T>(path, { body: patch })
        .then(() => {
          committed.current = optimistic;
          if (ticket < settled.current) return; // a newer save already landed
          settled.current = ticket;
          setStatus("saved");
        })
        .catch((cause: unknown) => {
          if (ticket < settled.current) return;
          settled.current = ticket;
          // Roll back to the server's truth, not to a guess.
          setValue(committed.current);
          setStatus("error");
          setError(
            cause instanceof ApiError
              ? cause.message
              : "บันทึกไม่สำเร็จ ลองอีกครั้งนะ",
          );
        });
    },
    [path, value],
  );

  return { value, update, status, error };
}

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/cn";

type Tone = "neutral" | "success" | "danger";

interface ToastItem {
  /** Dedupe identity  see `toast`'s `key` argument. */
  key: string;
  message: string;
  tone: Tone;
}

interface ToastContextValue {
  /**
   * Show a toast.
   *
   * `key` groups repeats of the *same* action. A second toast with a key
   * already on screen rewrites that one in place and restarts its timer
   * instead of stacking underneath it  so hammering a favourite button
   * flips one message back and forth rather than building a tower of
   * them. Omit `key` for one-off messages that should queue normally.
   */
  toast: (message: string, tone?: Tone, key?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TONES: Record<Tone, string> = {
  neutral: "border-edge bg-surface-raised text-fg",
  success: "border-success bg-success-subtle text-success",
  danger: "border-danger bg-danger-subtle text-danger",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const toast = useCallback(
    (message: string, tone: Tone = "neutral", key?: string) => {
      // Unkeyed toasts get a unique key, so they queue as they always did.
      const id = key ?? `auto-${nextId.current++}`;

      setItems((current) =>
        current.some((item) => item.key === id)
          ? current.map((item) =>
              item.key === id ? { ...item, message, tone } : item,
            )
          : [...current, { key: id, message, tone }],
      );

      // Restart the clock: the newest message gets its full five seconds
      // rather than inheriting what was left of the previous one's.
      const running = timers.current.get(id);
      if (running) clearTimeout(running);
      timers.current.set(
        id,
        setTimeout(() => {
          timers.current.delete(id);
          setItems((current) => current.filter((item) => item.key !== id));
        }, 5000),
      );
    },
    [],
  );

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4"
      >
        {items.map((item) => (
          <div
            key={item.key}
            role="status"
            className={cn(
              "pointer-events-auto w-full max-w-sm rounded-surface border px-4 py-3 text-sm shadow-overlay",
              TONES[item.tone],
            )}
          >
            {item.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside <ToastProvider>");
  return context;
}

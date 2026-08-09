"use client";

/**
 * The admin component system.
 *
 * A deliberately plain, dense counterpart to the learner UI: square-ish
 * corners, tabular numerals, muted surfaces, no decorative motion. Every
 * admin page composes these — no page defines its own table or toolbar.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/* ------------------------------------------------------------------ */
/* StatCard                                                            */
/* ------------------------------------------------------------------ */

export function StatCard({
  label,
  value,
  hint,
  loading,
  unavailable,
}: {
  label: string;
  value?: number | string | null;
  hint?: string;
  loading?: boolean;
  /** Why the number cannot be shown — rendered instead of a fake zero. */
  unavailable?: string;
}) {
  return (
    <div className="rounded-md border border-edge bg-surface-raised px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
        {label}
      </p>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-16" />
      ) : unavailable ? (
        <p className="mt-1 text-sm text-fg-subtle">— {unavailable}</p>
      ) : (
        <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-fg">
          {value ?? "—"}
        </p>
      )}
      {hint && !unavailable ? (
        <p className="mt-0.5 text-xs text-fg-muted">{hint}</p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* StatusBadge                                                         */
/* ------------------------------------------------------------------ */

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "bg-surface-sunken text-fg-muted",
  success: "bg-success-subtle text-success",
  warning: "bg-warning-subtle text-warning",
  danger: "bg-danger-subtle text-danger",
  info: "bg-lavender-soft text-lavender-ink",
};

/** Status vocabulary shared by every content app in this codebase. */
const STATUS_TONES: Record<string, Tone> = {
  published: "success",
  active: "success",
  valid: "success",
  completed: "success",
  draft: "warning",
  pending: "warning",
  open: "info",
  answered: "success",
  archived: "neutral",
  dropped: "neutral",
  hidden: "danger",
  removed: "danger",
  revoked: "danger",
  deleted: "danger",
  public: "success",
  unlisted: "warning",
  private: "neutral",
};

const STATUS_LABELS: Record<string, string> = {
  published: "เผยแพร่",
  draft: "ฉบับร่าง",
  archived: "เก็บเข้าคลัง",
  active: "ใช้งาน",
  hidden: "ซ่อน",
  removed: "ลบแล้ว",
  deleted: "ลบแล้ว",
  valid: "ใช้ได้",
  revoked: "เพิกถอน",
  public: "สาธารณะ",
  unlisted: "ไม่แสดงในรายการ",
  private: "ส่วนตัว",
  open: "ยังไม่มีคำตอบ",
  answered: "ตอบแล้ว",
  completed: "จบแล้ว",
  dropped: "ออกแล้ว",
  pending: "รอดำเนินการ",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONES[status] ?? "neutral";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium",
        TONE_CLASS[tone],
      )}
    >
      {/* A dot as well as colour: status must not be conveyed by hue alone. */}
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* SearchInput                                                         */
/* ------------------------------------------------------------------ */

export function SearchInput({
  value,
  onChange,
  placeholder = "ค้นหา…",
  label = "ค้นหา",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
}) {
  return (
    <div className="relative min-w-0 flex-1 sm:max-w-xs">
      <span
        aria-hidden
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-fg-subtle"
      >
        ⌕
      </span>
      <input
        type="search"
        aria-label={label}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-md border border-edge-strong/50 bg-surface pl-7 pr-3 text-sm text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus"
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* FilterBar                                                           */
/* ------------------------------------------------------------------ */

export interface FilterOption {
  value: string;
  label: string;
}

export function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-fg-muted">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-md border border-edge-strong/50 bg-surface px-2 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2">{children}</div>;
}

/** Toolbar above a table: search on the left, filters/actions on the right. */
export function DataTableToolbar({
  children,
  actions,
}: {
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-edge px-3 py-2.5">
      {children}
      {actions ? <div className="ml-auto flex gap-2">{actions}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* DataTable                                                           */
/* ------------------------------------------------------------------ */

export interface Column<T> {
  key: string;
  header: string;
  /** Right-aligned numeric columns get tabular figures. */
  numeric?: boolean;
  className?: string;
  render: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  empty,
  onRowClick,
  caption,
  /** Full-width management tables need room; panels in a split layout
      would otherwise clip their last column behind a scrollbar. */
  minWidthClass = "min-w-184",
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  loading?: boolean;
  empty?: ReactNode;
  onRowClick?: (row: T) => void;
  caption: string;
  minWidthClass?: string;
}) {
  if (loading) {
    return (
      <div aria-busy="true" className="space-y-2 p-3">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-9 w-full rounded" />
        ))}
      </div>
    );
  }
  if (rows.length === 0) return <div className="p-6">{empty}</div>;

  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full border-collapse text-sm", minWidthClass)}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-edge text-left">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  "whitespace-nowrap px-3 py-2 text-xs font-medium uppercase tracking-wide text-fg-subtle",
                  column.numeric && "text-right",
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(
                "border-b border-edge/60 align-middle",
                onRowClick && "cursor-pointer hover:bg-surface-sunken/60",
              )}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    "px-3 py-2 text-fg",
                    column.numeric && "text-right font-mono tabular-nums",
                    column.className,
                  )}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Pagination                                                          */
/* ------------------------------------------------------------------ */

export function Pagination({
  page,
  pageSize,
  count,
  onPage,
}: {
  page: number;
  pageSize: number;
  count: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (count === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-edge px-3 py-2.5 text-sm">
      <p className="text-xs text-fg-muted">
        แสดง <span className="font-mono tabular-nums">{from}</span>–
        <span className="font-mono tabular-nums">{to}</span> จาก{" "}
        <span className="font-mono tabular-nums">{count}</span> รายการ
      </p>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="secondary"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          ← ก่อนหน้า
        </Button>
        <span className="text-xs text-fg-muted">
          หน้า {page} / {pages}
        </span>
        <Button
          size="sm"
          variant="secondary"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          ถัดไป →
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Panels                                                              */
/* ------------------------------------------------------------------ */

export function AdminPanel({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "overflow-hidden rounded-md border border-edge bg-surface-raised",
        className,
      )}
    >
      {title ? (
        <header className="flex flex-wrap items-center gap-2 border-b border-edge px-3 py-2.5">
          <div>
            <h2 className="text-sm font-semibold text-fg">{title}</h2>
            {description ? (
              <p className="text-xs text-fg-muted">{description}</p>
            ) : null}
          </div>
          {actions ? <div className="ml-auto flex gap-2">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

/** Slide-over detail view — a dialog, so Escape and focus come free. */
export function DetailPanel({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      aria-label={title}
      className="m-0 ml-auto h-full max-h-full w-full max-w-xl border-l border-edge bg-surface p-0 shadow-overlay backdrop:bg-black/40"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-edge px-4 py-3">
          <h2 className="truncate text-sm font-semibold text-fg">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="ปิด"
            className="flex size-8 items-center justify-center rounded text-fg-muted hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
          >
            <span aria-hidden>✕</span>
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-4 text-sm">{children}</div>
        {footer ? (
          <footer className="flex flex-wrap justify-end gap-2 border-t border-edge px-4 py-3">
            {footer}
          </footer>
        ) : null}
      </div>
    </dialog>
  );
}

export function DetailRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-3 border-b border-edge/60 py-2">
      <dt className="text-xs uppercase tracking-wide text-fg-subtle">{label}</dt>
      <dd className="min-w-0 wrap-break-word text-fg">{children}</dd>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* ConfirmDialog                                                       */
/* ------------------------------------------------------------------ */

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  danger,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onCancel}
      aria-label={title}
      className="m-auto w-full max-w-sm rounded-md border border-edge bg-surface-raised p-0 shadow-overlay backdrop:bg-black/40"
    >
      <div className="px-4 py-4">
        <h2 className="text-sm font-semibold text-fg">{title}</h2>
        <div className="mt-2 text-sm text-fg-muted">{body}</div>
      </div>
      <div className="flex justify-end gap-2 border-t border-edge px-4 py-3">
        <Button size="sm" variant="secondary" onClick={onCancel}>
          ยกเลิก
        </Button>
        <Button
          size="sm"
          variant={danger ? "danger" : "primary"}
          loading={busy}
          onClick={onConfirm}
        >
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}

/** Wires a confirm dialog to an async action; returns the trigger. */
export function useConfirm() {
  const [state, setState] = useState<{
    title: string;
    body: ReactNode;
    confirmLabel: string;
    danger?: boolean;
    action: () => Promise<void>;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    if (!state) return;
    setBusy(true);
    try {
      await state.action();
    } finally {
      setBusy(false);
      setState(null);
    }
  }

  const dialog = (
    <ConfirmDialog
      open={state !== null}
      title={state?.title ?? ""}
      body={state?.body ?? null}
      confirmLabel={state?.confirmLabel ?? "ยืนยัน"}
      danger={state?.danger}
      busy={busy}
      onConfirm={confirm}
      onCancel={() => setState(null)}
    />
  );

  return { ask: setState, dialog };
}

/* ------------------------------------------------------------------ */
/* Empty / unavailable states                                          */
/* ------------------------------------------------------------------ */

export function AdminEmpty({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="py-8 text-center">
      <p className="text-sm font-medium text-fg">{title}</p>
      {description ? (
        <p className="mt-1 text-sm text-fg-muted">{description}</p>
      ) : null}
    </div>
  );
}

/**
 * The honest state for a capability the backend does not expose.
 *
 * Naming the missing endpoint is the point: an admin reading this knows
 * it is a backend gap, not a broken page, and a developer knows exactly
 * what would have to ship.
 */
export function UnavailablePanel({
  title,
  what,
  missing,
  workaround,
}: {
  title: string;
  what: string;
  missing: string[];
  workaround?: ReactNode;
}) {
  return (
    <AdminPanel title={title}>
      <div className="space-y-3 px-4 py-4 text-sm">
        <p className="text-fg-muted">{what}</p>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
            API ที่ยังไม่มีในระบบหลังบ้าน
          </p>
          <ul className="mt-1.5 space-y-1">
            {missing.map((item) => (
              <li
                key={item}
                className="flex gap-2 font-mono text-xs text-fg-muted"
              >
                <span aria-hidden className="text-warning">
                  ✗
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>
        {workaround ? (
          <div className="rounded border border-edge bg-surface-sunken/60 px-3 py-2 text-xs text-fg-muted">
            {workaround}
          </div>
        ) : null}
      </div>
    </AdminPanel>
  );
}

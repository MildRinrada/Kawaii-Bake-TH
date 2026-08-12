"use client";

/**
 * จัดการผู้ใช้ - the staff account workspace.
 *
 * Everything on this page is a real API operation:
 * - roster + filters: `GET /admin/users/` (search / status / verified /
 *   staff / joined_days / ordering, all validated server-side)
 * - summary cards: `GET /admin/users/stats/` - clicking one narrows the
 *   list to that population
 * - account creation + reset/verification emails: the ADR 0031 actions
 * - bulk actions: sequential per-row `PATCH`es with a per-batch failure
 *   report - there is no bulk endpoint, and this page does not pretend
 * - "role" is honest to the data model: staff flag or member. There is
 *   no stored learner/creator role; creator-ness shows as real activity
 *   counts instead. There is deliberately no delete - deactivation is
 *   the platform's soft path, and no delete endpoint exists.
 */

import { useRef, useState } from "react";

import { api } from "@/lib/api/client";
import type {
  AdminUser,
  AdminUserStats,
  RewardTransaction,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dropdown, type DropdownItem } from "@/components/ui/dropdown";
import { ErrorState } from "@/components/ui/error-state";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  FilterBar,
  FilterSelect,
  Pagination,
  SearchInput,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";
import { cn } from "@/lib/cn";

import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

import { CreateUserPanel } from "./create-user";
import { UserDetailPanel } from "./user-detail";

const STATUSES = [
  { value: "", label: "ทั้งหมด" },
  { value: "active", label: "ใช้งานอยู่" },
  { value: "suspended", label: "ปิดใช้งาน" },
];

const VERIFICATIONS = [
  { value: "", label: "ทั้งหมด" },
  { value: "true", label: "ยืนยันแล้ว" },
  { value: "false", label: "รอยืนยัน" },
];

const ROLES = [
  { value: "", label: "ทุกบทบาท" },
  { value: "true", label: "ผู้ดูแล" },
  { value: "false", label: "สมาชิก" },
];

const JOINED = [
  { value: "", label: "ทุกช่วงเวลา" },
  { value: "7", label: "7 วันล่าสุด" },
  { value: "30", label: "30 วันล่าสุด" },
  { value: "90", label: "90 วันล่าสุด" },
];

const ORDERINGS = [
  { value: "newest", label: "สมัครล่าสุด" },
  { value: "oldest", label: "สมัครเก่าสุด" },
  { value: "username", label: "ชื่อผู้ใช้ ก-ฮ" },
  { value: "recently_active", label: "ใช้งานล่าสุด" },
];

const PAGE_SIZES = [10, 25, 50];

/** Role, honest to the data model: superuser / staff / member. */
function RoleBadge({ user }: { user: AdminUser }) {
  if (user.is_superuser) return <Badge tone="berry">ผู้ดูแลสูงสุด</Badge>;
  if (user.is_staff) return <Badge tone="lavender">ผู้ดูแล</Badge>;
  return <Badge tone="neutral">สมาชิก</Badge>;
}

/** One derived account state: deactivated beats pending beats active. */
function AccountStatusBadge({ user }: { user: AdminUser }) {
  if (!user.is_active) return <Badge tone="danger">ปิดใช้งาน</Badge>;
  if (!user.is_email_verified)
    return <Badge tone="warning">รอยืนยันอีเมล</Badge>;
  return <Badge tone="success">ใช้งานอยู่</Badge>;
}

function ActivityCell({ user }: { user: AdminUser }) {
  const parts = [
    user.courses_count ? `เรียน ${user.courses_count} คอร์ส` : null,
    user.recipes_count ? `สูตร ${user.recipes_count}` : null,
    user.posts_count ? `โพสต์ ${user.posts_count}` : null,
  ].filter(Boolean);
  return (
    <span className="whitespace-nowrap text-xs text-fg-muted">
      {parts.length ? parts.join(" · ") : "-"}
    </span>
  );
}

function UserCell({ user }: { user: AdminUser }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <Avatar
        src={user.avatar_url}
        name={user.display_name || user.username}
        size="sm"
      />
      <div className="min-w-0">
        <p className="line-clamp-1 font-medium">
          {user.display_name || user.username}
        </p>
        <p className="line-clamp-1 font-mono text-xs text-fg-subtle">
          @{user.username} · {user.email}
        </p>
      </div>
    </div>
  );
}

export default function AdminUsersPage() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const { user: caller } = useAuth();

  // ---- filters ----------------------------------------------------
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [status, setStatus] = useState("");
  const [verified, setVerified] = useState("");
  const [staff, setStaff] = useState("");
  const [joined, setJoined] = useState("");
  const [ordering, setOrdering] = useState("newest");
  const [pageSize, setPageSize] = useState(25);

  const hasFilters =
    Boolean(search) || Boolean(status) || Boolean(verified) || Boolean(staff) || Boolean(joined);

  function clearFilters() {
    setSearchInput("");
    setStatus("");
    setVerified("");
    setStaff("");
    setJoined("");
  }

  const stats = useApiQuery(
    (signal) => api.get<AdminUserStats>("/admin/users/stats/", { signal }),
    [],
  );
  const list = usePagedList<AdminUser>("/admin/users/", {
    ordering,
    page_size: pageSize,
    search: search || undefined,
    status: status || undefined,
    verified: verified || undefined,
    staff: staff || undefined,
    joined_days: joined || undefined,
  });

  // ---- selection (bulk) -------------------------------------------
  // Reset whenever the visible rows change - render-time, no effect.
  const listKey = list.rows.map((row) => row.id).join(",");
  const [selectionKey, setSelectionKey] = useState(listKey);
  const [checked, setChecked] = useState<ReadonlySet<number>>(new Set());
  if (selectionKey !== listKey) {
    setSelectionKey(listKey);
    setChecked(new Set());
  }

  const [selected, setSelected] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);

  // Reward adjustment - the page's original write; the drawer's footer
  // button pre-fills its username field.
  const rewardsRef = useRef<HTMLElement>(null);
  const [adjustUser, setAdjustUser] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [lastAdjustment, setLastAdjustment] =
    useState<RewardTransaction | null>(null);

  async function adjust() {
    try {
      const row = await api.post<RewardTransaction>("/rewards/adjustments/", {
        body: {
          username: adjustUser.trim(),
          amount: Number(amount),
          reason: reason.trim(),
        },
      });
      setLastAdjustment(row);
      setAmount("");
      setReason("");
      toast("บันทึกการปรับยอดลงบัญชีแล้ว", "success");
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  function prefillAdjust(username: string) {
    setAdjustUser(username);
    setSelected(null);
    // Let the dialog finish closing before scrolling to the panel it
    // just pointed the admin at.
    requestAnimationFrame(() =>
      rewardsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  }

  const amountValid = amount.trim() !== "" && Number.isFinite(Number(amount));

  function toggleRow(id: number, next: boolean) {
    setChecked((current) => {
      const draft = new Set(current);
      if (next) draft.add(id);
      else draft.delete(id);
      return draft;
    });
  }

  function toggleAll(next: boolean) {
    setChecked(next ? new Set(list.rows.map((row) => row.id)) : new Set());
  }

  function refresh() {
    list.refetch();
    stats.refetch();
  }

  /**
   * Run one real call per selected row, sequentially, and report the
   * batch honestly - skipped rows (already in the target state, or the
   * caller's own account) are named, and failures never stop the rest.
   */
  async function runBulk(
    label: string,
    eligible: (row: AdminUser) => boolean,
    action: (row: AdminUser) => Promise<unknown>,
  ) {
    const rows = list.rows.filter((row) => checked.has(row.id));
    const skipped = rows.filter((row) => !eligible(row));
    const targets = rows.filter(eligible);
    setBulkBusy(true);
    const failures: string[] = [];
    for (const row of targets) {
      try {
        await action(row);
      } catch {
        failures.push(`@${row.username}`);
      }
    }
    setBulkBusy(false);
    refresh();
    const doneCount = targets.length - failures.length;
    let message = `${label} ${doneCount} บัญชีแล้ว`;
    if (skipped.length)
      message += ` (ข้าม ${skipped.length} ที่ไม่เข้าเงื่อนไข)`;
    if (failures.length)
      message += ` - ล้มเหลว: ${failures.join(", ")}`;
    toast(message, failures.length ? "danger" : "success");
  }

  function bulkDeactivate() {
    const count = checked.size;
    confirm.ask({
      title: `ปิดการใช้งาน ${count} บัญชี?`,
      body: "ผู้ใช้ที่เลือกจะเข้าสู่ระบบไม่ได้จนกว่าจะเปิดใช้งานคืน เนื้อหาที่เคยสร้างยังอยู่ครบ - บัญชีของคุณเองและผู้ดูแลสูงสุดจะถูกข้าม",
      confirmLabel: "ปิดการใช้งาน",
      danger: true,
      action: () =>
        runBulk(
          "ปิดการใช้งาน",
          (row) =>
            row.is_active &&
            !row.is_superuser &&
            row.username !== caller?.username,
          (row) =>
            api.patch(`/admin/users/${row.id}/`, {
              body: { is_active: false },
            }),
        ),
    });
  }

  function bulkReactivate() {
    void runBulk(
      "เปิดใช้งาน",
      (row) => !row.is_active && !row.is_superuser,
      (row) =>
        api.patch(`/admin/users/${row.id}/`, { body: { is_active: true } }),
    );
  }

  function bulkResendVerification() {
    void runBulk(
      "ส่งอีเมลยืนยันให้",
      (row) => row.is_active && !row.is_email_verified,
      (row) => api.post(`/admin/users/${row.id}/resend-verification/`),
    );
  }

  // ---- row actions ------------------------------------------------
  async function sendEmail(row: AdminUser, kind: "reset" | "verify") {
    try {
      await api.post(
        kind === "reset"
          ? `/admin/users/${row.id}/send-password-reset/`
          : `/admin/users/${row.id}/resend-verification/`,
      );
      toast(
        kind === "reset"
          ? `ส่งลิงก์รีเซ็ตรหัสผ่านให้ @${row.username} แล้ว`
          : `ส่งอีเมลยืนยันให้ @${row.username} อีกครั้งแล้ว`,
        "success",
      );
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  async function setActive(row: AdminUser, next: boolean) {
    try {
      await api.patch(`/admin/users/${row.id}/`, {
        body: { is_active: next },
      });
      toast(
        next
          ? `เปิดใช้งาน @${row.username} แล้ว`
          : `ปิดการใช้งาน @${row.username} แล้ว`,
        "success",
      );
      refresh();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  function rowMenu(row: AdminUser): DropdownItem[] {
    const isSelf = row.username === caller?.username;
    const items: DropdownItem[] = [
      {
        key: "view",
        label: "ดูโปรไฟล์และแก้ไข",
        onSelect: () => setSelected(row.id),
      },
    ];
    if (row.is_active) {
      items.push({
        key: "reset",
        label: "ส่งลิงก์รีเซ็ตรหัสผ่าน",
        onSelect: () => void sendEmail(row, "reset"),
      });
      if (!row.is_email_verified) {
        items.push({
          key: "verify",
          label: "ส่งอีเมลยืนยันอีกครั้ง",
          onSelect: () => void sendEmail(row, "verify"),
        });
      }
    }
    if (!row.is_superuser && !isSelf) {
      if (row.is_active) {
        items.push({
          key: "deactivate",
          label: <span className="text-danger">ปิดการใช้งาน</span>,
          separator: true,
          onSelect: () =>
            confirm.ask({
              title: `ปิดการใช้งาน @${row.username}?`,
              body: "ผู้ใช้จะเข้าสู่ระบบไม่ได้จนกว่าจะเปิดใช้งานคืน เนื้อหาที่เคยสร้างยังอยู่ครบ",
              confirmLabel: "ปิดการใช้งาน",
              danger: true,
              action: () => setActive(row, false),
            }),
        });
      } else {
        items.push({
          key: "reactivate",
          label: "เปิดใช้งานอีกครั้ง",
          separator: true,
          onSelect: () => void setActive(row, true),
        });
      }
    }
    return items;
  }

  // ---- stat cards as narrow filters -------------------------------
  const cards = [
    {
      key: "total",
      label: "ผู้ใช้ทั้งหมด",
      value: stats.data?.total,
      hint: stats.data ? `ใหม่ใน 7 วัน +${stats.data.new_7d}` : undefined,
      active: !status && verified === "",
      apply: () => {
        setStatus("");
        setVerified("");
      },
    },
    {
      key: "active",
      label: "ใช้งานอยู่",
      value: stats.data?.active,
      active: status === "active" && verified === "",
      apply: () => {
        setStatus("active");
        setVerified("");
      },
    },
    {
      key: "pending",
      label: "รอยืนยันอีเมล",
      value: stats.data?.pending,
      active: status === "active" && verified === "false",
      apply: () => {
        setStatus("active");
        setVerified("false");
      },
    },
    {
      key: "suspended",
      label: "ถูกปิดใช้งาน",
      value: stats.data?.suspended,
      active: status === "suspended",
      apply: () => {
        setStatus("suspended");
        setVerified("");
      },
    },
  ];

  const from = list.count === 0 ? 0 : (list.page - 1) * list.pageSize + 1;
  const to = Math.min(list.page * list.pageSize, list.count);

  if (list.error) {
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="จัดการผู้ใช้"
        description="ค้นหา ตรวจสอบสถานะและบทบาท จัดการสิทธิ์ และเปิด/ปิดการใช้งานบัญชีผู้ใช้ KawaiiBake"
        actions={
          <Button size="sm" onClick={() => setCreating(true)}>
            + เพิ่มผู้ใช้
          </Button>
        }
      />

      {/* ---- summary cards: click to narrow ---- */}
      <div className="mb-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
        {cards.map((card) => (
          <button
            key={card.key}
            type="button"
            aria-pressed={card.active}
            onClick={card.apply}
            className={cn(
              "rounded-md border px-4 py-3 text-left transition-colors",
              card.active
                ? "border-accent bg-accent-subtle"
                : "border-edge bg-surface-raised hover:border-edge-strong",
            )}
          >
            <p className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
              {card.label}
            </p>
            <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-fg">
              {stats.loading ? "…" : (card.value ?? "-")}
            </p>
            {card.hint ? (
              <p className="mt-0.5 text-xs text-fg-muted">{card.hint}</p>
            ) : null}
          </button>
        ))}
      </div>

      <AdminPanel>
        <DataTableToolbar
          actions={
            <div className="flex items-center gap-2 self-center">
              {hasFilters ? (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="text-xs text-accent hover:underline"
                >
                  ล้างตัวกรอง
                </button>
              ) : null}
              <span className="text-xs text-fg-muted">
                ทั้งหมด{" "}
                <span className="font-mono tabular-nums">{list.count}</span> คน
              </span>
            </div>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหาชื่อ, username หรืออีเมล…"
            label="ค้นหาผู้ใช้"
          />
          <FilterBar>
            <FilterSelect
              label="บทบาท"
              value={staff}
              options={ROLES}
              onChange={setStaff}
            />
            <FilterSelect
              label="สถานะ"
              value={status}
              options={STATUSES}
              onChange={setStatus}
            />
            <FilterSelect
              label="อีเมล"
              value={verified}
              options={VERIFICATIONS}
              onChange={setVerified}
            />
            <FilterSelect
              label="สมัครเมื่อ"
              value={joined}
              options={JOINED}
              onChange={setJoined}
            />
            <FilterSelect
              label="เรียงตาม"
              value={ordering}
              options={ORDERINGS}
              onChange={setOrdering}
            />
          </FilterBar>
        </DataTableToolbar>

        {/* ---- contextual bulk bar ---- */}
        {checked.size > 0 ? (
          <div
            role="region"
            aria-label="การจัดการแบบกลุ่ม"
            className="flex flex-wrap items-center gap-2 border-b border-edge bg-accent-subtle/60 px-4 py-2"
          >
            <span className="text-sm font-medium">
              เลือกแล้ว {checked.size} คน
            </span>
            <div className="ml-auto flex flex-wrap gap-1.5">
              <Button
                size="sm"
                variant="secondary"
                disabled={bulkBusy}
                onClick={bulkResendVerification}
              >
                ส่งอีเมลยืนยันอีกครั้ง
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={bulkBusy}
                onClick={bulkReactivate}
              >
                เปิดใช้งานอีกครั้ง
              </Button>
              <Button
                size="sm"
                variant="danger"
                disabled={bulkBusy}
                loading={bulkBusy}
                onClick={bulkDeactivate}
              >
                ปิดการใช้งาน
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={bulkBusy}
                onClick={() => toggleAll(false)}
              >
                ล้างการเลือก
              </Button>
            </div>
          </div>
        ) : null}

        {/* ---- desktop table ---- */}
        <div className="hidden md:block">
          <DataTable
            caption="รายชื่อผู้ใช้ทั้งหมด"
            loading={list.loading}
            rows={list.rows}
            rowKey={(row) => row.id}
            onRowClick={(row) => setSelected(row.id)}
            empty={
              <AdminEmpty
                title={hasFilters ? "ไม่พบผู้ใช้" : "ยังไม่มีผู้ใช้"}
                description={
                  hasFilters
                    ? "ลองเปลี่ยนคำค้นหาหรือตัวกรองของคุณ"
                    : "กด “+ เพิ่มผู้ใช้” เพื่อสร้างบัญชีแรก"
                }
              />
            }
            columns={[
              {
                key: "check",
                header: (
                  <input
                    type="checkbox"
                    aria-label="เลือกทุกแถวในหน้านี้"
                    className="size-4 accent-(--color-accent)"
                    checked={
                      list.rows.length > 0 && checked.size === list.rows.length
                    }
                    onChange={(event) => toggleAll(event.target.checked)}
                  />
                ),
                className: "w-10",
                render: (row) => (
                  <input
                    type="checkbox"
                    aria-label={`เลือก @${row.username}`}
                    className="size-4 accent-(--color-accent)"
                    checked={checked.has(row.id)}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => toggleRow(row.id, event.target.checked)}
                  />
                ),
              },
              {
                key: "user",
                header: "ผู้ใช้",
                render: (row) => <UserCell user={row} />,
              },
              {
                key: "role",
                header: "บทบาท",
                render: (row) => <RoleBadge user={row} />,
              },
              {
                key: "status",
                header: "สถานะ",
                render: (row) => <AccountStatusBadge user={row} />,
              },
              {
                key: "joined",
                header: "สมัครเมื่อ",
                render: (row) => (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {relativeThai(row.created_at)}
                  </span>
                ),
              },
              {
                key: "last_active",
                header: "ใช้งานล่าสุด",
                render: (row) => (
                  <span className="whitespace-nowrap text-xs text-fg-muted">
                    {row.last_login ? relativeThai(row.last_login) : "-"}
                  </span>
                ),
              },
              {
                key: "activity",
                header: "กิจกรรม",
                render: (row) => <ActivityCell user={row} />,
              },
              {
                key: "actions",
                header: "การจัดการ",
                className: "w-px",
                render: (row) => (
                  <div
                    className="flex items-center gap-1.5"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <button
                      type="button"
                      onClick={() => setSelected(row.id)}
                      className="whitespace-nowrap rounded border border-edge-strong/60 px-2.5 py-1 text-xs text-fg hover:bg-accent-subtle"
                    >
                      จัดการ
                    </button>
                    <Dropdown
                      trigger={
                        <span className="px-2 py-1 text-fg-muted">…</span>
                      }
                      items={rowMenu(row)}
                    />
                  </div>
                ),
              },
            ]}
          />
        </div>

        {/* ---- mobile cards ---- */}
        <ul className="divide-y divide-edge md:hidden">
          {list.rows.map((row) => (
            <li key={row.id} className="flex items-start gap-3 px-4 py-3">
              <input
                type="checkbox"
                aria-label={`เลือก @${row.username}`}
                className="mt-2 size-4 accent-(--color-accent)"
                checked={checked.has(row.id)}
                onChange={(event) => toggleRow(row.id, event.target.checked)}
              />
              <button
                type="button"
                onClick={() => setSelected(row.id)}
                className="min-w-0 flex-1 text-left"
              >
                <UserCell user={row} />
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <RoleBadge user={row} />
                  <AccountStatusBadge user={row} />
                  <span className="text-xs text-fg-subtle">
                    {relativeThai(row.created_at)}
                  </span>
                </div>
                <div className="mt-1">
                  <ActivityCell user={row} />
                </div>
              </button>
              <Dropdown
                trigger={<span className="px-2 py-1 text-fg-muted">…</span>}
                items={rowMenu(row)}
              />
            </li>
          ))}
          {!list.loading && list.rows.length === 0 ? (
            <li>
              <AdminEmpty
                title={hasFilters ? "ไม่พบผู้ใช้" : "ยังไม่มีผู้ใช้"}
                description="ลองเปลี่ยนคำค้นหาหรือตัวกรองของคุณ"
              />
            </li>
          ) : null}
        </ul>

        {/* ---- pagination + rows per page ---- */}
        <div className="flex flex-wrap items-center gap-2 border-t border-edge px-4 py-2">
          <span className="text-xs text-fg-muted">
            แสดง {from.toLocaleString("th-TH")}–{to.toLocaleString("th-TH")}{" "}
            จาก {list.count.toLocaleString("th-TH")} คน
          </span>
          <label className="ml-auto flex items-center gap-1.5 text-xs text-fg-muted">
            ต่อหน้า
            <select
              value={pageSize}
              onChange={(event) => setPageSize(Number(event.target.value))}
              className="rounded border border-edge bg-surface px-1.5 py-1 text-xs"
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Pagination
          page={list.page}
          pageSize={list.pageSize}
          count={list.count}
          onPage={list.setPage}
        />
      </AdminPanel>

      <p className="mt-3 text-xs text-fg-muted">
        บทบาทเป็นไปตามข้อมูลจริงของระบบ (ผู้ดูแล/สมาชิก) - ความเป็น
        “ผู้สร้างสูตร” แสดงผ่านตัวเลขกิจกรรมจริงแทนป้ายบทบาท และไม่มีปุ่มลบบัญชี:
        การปิดใช้งานคือเส้นทางที่ปลอดภัย เนื้อหาและประวัติผู้ใช้ยังอยู่ครบ
      </p>

      <section ref={rewardsRef} className="mt-4 scroll-mt-4">
        <AdminPanel
          title="ปรับยอดคะแนนรางวัล"
          description="POST /rewards/adjustments/ - staff เท่านั้น บันทึกลงบัญชีแบบตรวจสอบย้อนหลังได้"
        >
          <div className="px-4 py-4">
            <div className="grid gap-3 md:grid-cols-3">
              <Field
                label="username ปลายทาง"
                hint="กดปุ่มในหน้ารายละเอียดผู้ใช้เพื่อเติมให้อัตโนมัติ"
              >
                {(control) => (
                  <Input
                    {...control}
                    value={adjustUser}
                    placeholder="ผู้ใช้ที่จะปรับยอด"
                    onChange={(event) => setAdjustUser(event.target.value)}
                  />
                )}
              </Field>
              <Field
                label="จำนวน (ติดลบได้)"
                hint="จำนวนเต็ม - ค่าติดลบคือการหักคืน"
              >
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                  />
                )}
              </Field>
              <Field label="เหตุผล" hint="บันทึกลงประวัติถาวร">
                {(control) => (
                  <Input
                    {...control}
                    value={reason}
                    placeholder="เช่น ชดเชยคะแนนที่หายจากบั๊ก"
                    onChange={(event) => setReason(event.target.value)}
                  />
                )}
              </Field>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button
                disabled={!adjustUser.trim() || !amountValid || !reason.trim()}
                onClick={() =>
                  confirm.ask({
                    title: "ยืนยันการปรับยอด?",
                    body: `จะปรับยอดของ @${adjustUser.trim()} เป็นจำนวน ${amount} คะแนน พร้อมเหตุผล “${reason.trim()}” - รายการนี้ลงบัญชีถาวรและลบไม่ได้`,
                    confirmLabel: "ยืนยันปรับยอด",
                    danger: Number(amount) < 0,
                    action: adjust,
                  })
                }
              >
                ปรับยอด
              </Button>

              {lastAdjustment ? (
                <div className="rounded border border-edge bg-surface-sunken/60 px-3 py-2 text-xs">
                  <p className="font-medium text-fg">รายการล่าสุดที่บันทึก</p>
                  <p className="mt-1 font-mono text-fg-muted">
                    {lastAdjustment.amount > 0 ? "+" : ""}
                    {lastAdjustment.amount} → ยอดคงเหลือ{" "}
                    {lastAdjustment.balance_after} · โดย{" "}
                    {lastAdjustment.actor_handle}
                  </p>
                </div>
              ) : null}
            </div>
          </div>
        </AdminPanel>
      </section>

      {/* Mounted only while open, so each visit starts a fresh form. */}
      {creating ? (
        <CreateUserPanel
          open
          onClose={() => setCreating(false)}
          onCreated={refresh}
        />
      ) : null}

      <UserDetailPanel
        userId={selected}
        onClose={() => setSelected(null)}
        onChanged={refresh}
        onAdjustRewards={prefillAdjust}
      />

      {confirm.dialog}
    </>
  );
}

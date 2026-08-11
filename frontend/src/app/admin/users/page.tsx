"use client";

/**
 * User roster management.
 *
 * `GET /admin/users/` is the staff-only roster: search covers username /
 * email / legal name / display name, and the status, verification and
 * staff filters map one-to-one onto the query keys the backend actually
 * validates - unknown keys are rejected with 400, so empty filters are
 * omitted rather than sent blank.
 *
 * Per-account editing lives in the slide-over (`./user-detail`). The
 * auditable reward adjustment (`POST /rewards/adjustments/`, the page's
 * original write) keeps its panel below the roster - the detail footer
 * pre-fills its username field.
 */

import { useRef, useState } from "react";

import { api } from "@/lib/api/client";
import type { AdminUser, RewardTransaction } from "@/lib/api/models";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
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

import { AccountBadges, UserDetailPanel, fullName } from "./user-detail";

const STATUSES = [
  { value: "", label: "ทั้งหมด" },
  { value: "active", label: "ใช้งาน" },
  { value: "suspended", label: "ระงับ" },
];

const VERIFICATIONS = [
  { value: "", label: "ทั้งหมด" },
  { value: "true", label: "ยืนยันแล้ว" },
  { value: "false", label: "ยังไม่ยืนยัน" },
];

const ROLES = [
  { value: "", label: "ทั้งหมด" },
  { value: "true", label: "สตาฟ" },
  { value: "false", label: "สมาชิกทั่วไป" },
];

const ORDERINGS = [
  { value: "newest", label: "ใหม่สุด" },
  { value: "oldest", label: "เก่าสุด" },
  { value: "username", label: "ชื่อผู้ใช้" },
  { value: "recently_active", label: "ใช้งานล่าสุด" },
];

export default function AdminUsersPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [status, setStatus] = useState("");
  const [verified, setVerified] = useState("");
  const [staff, setStaff] = useState("");
  const [ordering, setOrdering] = useState("newest");
  const [selected, setSelected] = useState<number | null>(null);

  const list = usePagedList<AdminUser>("/admin/users/", {
    ordering,
    search: search || undefined,
    status: status || undefined,
    verified: verified || undefined,
    staff: staff || undefined,
  });

  // Reward adjustment - carried over from the pre-roster version of this
  // page; still the only write that touches the reward ledger.
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

  if (list.error) {
    return <ErrorState error={list.error} onRetry={list.refetch} />;
  }

  return (
    <>
      <AdminPageHeader
        title="ผู้ใช้"
        description="รายชื่อผู้ใช้ทั้งระบบ - ค้นหา กรองสถานะบัญชี แก้ชื่อ ระงับ/เปิดใช้งาน ให้สิทธิ์สตาฟ และปรับยอดคะแนนรางวัล"
      />

      <AdminPanel>
        <DataTableToolbar
          actions={
            <span className="self-center text-xs text-fg-muted">
              ทั้งหมด{" "}
              <span className="font-mono tabular-nums">{list.count}</span> บัญชี
            </span>
          }
        >
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="ค้นหา username อีเมล หรือชื่อ…"
            label="ค้นหาผู้ใช้"
          />
          <FilterBar>
            <FilterSelect
              label="สถานะบัญชี"
              value={status}
              options={STATUSES}
              onChange={setStatus}
            />
            <FilterSelect
              label="การยืนยันอีเมล"
              value={verified}
              options={VERIFICATIONS}
              onChange={setVerified}
            />
            <FilterSelect
              label="สิทธิ์"
              value={staff}
              options={ROLES}
              onChange={setStaff}
            />
            <FilterSelect
              label="เรียงตาม"
              value={ordering}
              options={ORDERINGS}
              onChange={setOrdering}
            />
          </FilterBar>
        </DataTableToolbar>

        <DataTable
          caption="รายชื่อผู้ใช้ทั้งหมด"
          loading={list.loading}
          rows={list.rows}
          rowKey={(row) => row.id}
          onRowClick={(row) => setSelected(row.id)}
          empty={
            <AdminEmpty
              title="ไม่พบผู้ใช้ที่ตรงกับเงื่อนไข"
              description="ลองล้างคำค้นหรือเปลี่ยนตัวกรอง"
            />
          }
          columns={[
            {
              key: "avatar",
              header: "",
              className: "w-14",
              render: (row) => (
                <Avatar
                  src={row.avatar_url}
                  name={row.display_name || row.username}
                  size="sm"
                />
              ),
            },
            {
              key: "user",
              header: "ผู้ใช้",
              render: (row) => (
                <div className="min-w-0">
                  <p className="line-clamp-1 font-medium">
                    {row.display_name || row.username}
                  </p>
                  <p className="font-mono text-xs text-fg-subtle">
                    @{row.username} · {row.email}
                  </p>
                </div>
              ),
            },
            {
              key: "legal_name",
              header: "ชื่อจริง",
              render: (row) => (
                <span className="text-fg-muted">{fullName(row) ?? "-"}</span>
              ),
            },
            {
              key: "experience",
              header: "ระดับฝีมือ",
              render: (row) => (
                <span className="text-xs text-fg-muted">
                  {row.experience_level || "-"}
                </span>
              ),
            },
            {
              key: "status",
              header: "สถานะ",
              render: (row) => (
                <div className="flex flex-wrap gap-1">
                  <AccountBadges user={row} />
                </div>
              ),
            },
            {
              key: "joined",
              header: "เข้าร่วมเมื่อ",
              render: (row) => (
                <span className="whitespace-nowrap text-xs text-fg-muted">
                  {relativeThai(row.created_at)}
                </span>
              ),
            },
            {
              key: "last_login",
              header: "เข้าสู่ระบบล่าสุด",
              render: (row) => (
                <span className="whitespace-nowrap text-xs text-fg-muted">
                  {row.last_login ? relativeThai(row.last_login) : "-"}
                </span>
              ),
            },
          ]}
        />

        <Pagination
          page={list.page}
          pageSize={list.pageSize}
          count={list.count}
          onPage={list.setPage}
        />
      </AdminPanel>

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

      <UserDetailPanel
        userId={selected}
        onClose={() => setSelected(null)}
        onChanged={list.refetch}
        onAdjustRewards={prefillAdjust}
      />

      {confirm.dialog}
    </>
  );
}

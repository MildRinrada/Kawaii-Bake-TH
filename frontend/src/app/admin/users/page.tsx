"use client";

/**
 * Users.
 *
 * There is no user-administration API in this backend: no roster, no
 * account-status endpoint, no way to deactivate somebody else
 * (`/users/account/deactivate/` acts on the caller alone). What exists
 * is `GET /users/{username}/` — a *public* profile, already filtered by
 * that user's own privacy settings — so this page is a lookup, and says
 * so.
 *
 * The one real staff-only write in the whole API lives here:
 * `POST /rewards/adjustments/` (`IsAdminUser`), an auditable, idempotent
 * balance correction. It is presented with a confirmation step because
 * it writes to a ledger.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { PublicProfile, RewardTransaction } from "@/lib/api/models";
import { useToast } from "@/components/ui/toast";
import { monthYearThai } from "@/lib/datetime";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminPanel,
  DetailRow,
  UnavailablePanel,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

export default function AdminUsersPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [handle, setHandle] = useState("");
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [looking, setLooking] = useState(false);

  const [adjustUser, setAdjustUser] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [lastAdjustment, setLastAdjustment] = useState<RewardTransaction | null>(
    null,
  );

  async function lookup(event: React.FormEvent) {
    event.preventDefault();
    const username = handle.trim();
    if (!username) return;
    setLooking(true);
    setLookupError(null);
    setProfile(null);
    try {
      const found = await api.get<PublicProfile>(`/users/${username}/`);
      setProfile(found);
      setAdjustUser(found.username);
    } catch (error) {
      setProfile(null);
      setLookupError(
        error instanceof ApiError && error.status === 404
          ? "ไม่พบผู้ใช้ชื่อนี้ หรือโปรไฟล์ถูกตั้งเป็นส่วนตัว"
          : describeAdminError(error),
      );
    } finally {
      setLooking(false);
    }
  }

  async function adjust() {
    const parsed = Number(amount);
    try {
      const row = await api.post<RewardTransaction>("/rewards/adjustments/", {
        body: {
          username: adjustUser.trim(),
          amount: parsed,
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

  const amountValid = amount.trim() !== "" && Number.isFinite(Number(amount));

  return (
    <>
      <AdminPageHeader
        title="ผู้ใช้"
        description="ค้นหาผู้ใช้ทีละคนจากโปรไฟล์สาธารณะ และปรับยอดคะแนนรางวัลด้วยสิทธิ์ staff"
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <AdminPanel
          title="ค้นหาผู้ใช้"
          description="ค้นจาก username เท่านั้น — API ไม่มีรายชื่อผู้ใช้ทั้งระบบ"
        >
          <div className="px-4 py-4">
            <form onSubmit={lookup} className="flex items-end gap-2" noValidate>
              <Field label="username" className="flex-1">
                {(control) => (
                  <Input
                    {...control}
                    value={handle}
                    placeholder="เช่น mildbakes"
                    onChange={(event) => setHandle(event.target.value)}
                  />
                )}
              </Field>
              <Button type="submit" loading={looking}>
                ค้นหา
              </Button>
            </form>

            {lookupError ? (
              <p role="alert" className="mt-3 text-sm text-danger">
                {lookupError}
              </p>
            ) : null}

            {profile ? (
              <div className="mt-4">
                <div className="flex items-center gap-3">
                  <Avatar
                    src={profile.avatar_url}
                    name={profile.display_name || profile.username}
                  />
                  <div>
                    <p className="font-medium text-fg">
                      {profile.display_name || profile.username}
                    </p>
                    <p className="font-mono text-xs text-fg-subtle">
                      @{profile.username}
                    </p>
                  </div>
                </div>
                <dl className="mt-3">
                  <DetailRow label="แนะนำตัว">{profile.bio || "—"}</DetailRow>
                  <DetailRow label="ระดับฝีมือ">
                    <Badge tone="lavender">{profile.experience_level}</Badge>
                  </DetailRow>
                  <DetailRow label="หมวดที่สนใจ">
                    {profile.favorite_categories.join(", ") || "—"}
                  </DetailRow>
                  <DetailRow label="ที่อยู่">
                    {profile.location ?? "ผู้ใช้ตั้งเป็นส่วนตัว"}
                  </DetailRow>
                  <DetailRow label="เข้าร่วมเมื่อ">
                    {monthYearThai(profile.joined_at)}
                  </DetailRow>
                </dl>
                <p className="mt-3 text-xs text-fg-muted">
                  นี่คือโปรไฟล์สาธารณะที่ผ่านการกรองด้วยการตั้งค่าความเป็นส่วนตัวของเจ้าของแล้ว
                  — อีเมลและข้อมูลบัญชีไม่เคยถูกส่งมาที่ client
                </p>
              </div>
            ) : null}
          </div>
        </AdminPanel>

        <AdminPanel
          title="ปรับยอดคะแนนรางวัล"
          description="POST /rewards/adjustments/ — staff เท่านั้น บันทึกลงบัญชีแบบตรวจสอบย้อนหลังได้"
        >
          <div className="space-y-3 px-4 py-4">
            <Field label="username ปลายทาง">
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
              hint="จำนวนเต็ม — ค่าติดลบคือการหักคืน"
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
            <Button
              disabled={!adjustUser.trim() || !amountValid || !reason.trim()}
              onClick={() =>
                confirm.ask({
                  title: "ยืนยันการปรับยอด?",
                  body: `จะปรับยอดของ @${adjustUser.trim()} เป็นจำนวน ${amount} คะแนน พร้อมเหตุผล “${reason.trim()}” — รายการนี้ลงบัญชีถาวรและลบไม่ได้`,
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
        </AdminPanel>
      </div>

      <div className="mt-4">
        <UnavailablePanel
          title="การจัดการบัญชีผู้ใช้"
          what="ระบบหลังบ้านยังไม่มี API สำหรับผู้ดูแลจัดการบัญชีผู้อื่น จึงไม่มีตารางรายชื่อผู้ใช้ ตัวกรองสถานะบัญชี หรือปุ่มระงับ/เปิดใช้งานในหน้านี้ — และจะไม่ใส่ปุ่มหลอกไว้"
          missing={[
            "GET /api/v1/users/ (รายชื่อผู้ใช้พร้อมค้นหาและแบ่งหน้า)",
            "GET /api/v1/users/{username}/admin/ (ข้อมูลบัญชี: สถานะ, วันเข้าใช้ล่าสุด, การยืนยันอีเมล)",
            "POST /api/v1/users/{username}/deactivate/ (ระงับบัญชีผู้อื่น)",
            "PATCH สิทธิ์ staff / กลุ่มผู้ใช้",
          ]}
          workaround="ระหว่างนี้จัดการบัญชีได้ที่ Django Admin ฝั่งเซิร์ฟเวอร์เท่านั้น การค้นหาด้านบนใช้ endpoint โปรไฟล์สาธารณะซึ่งไม่ส่งอีเมลหรือข้อมูลลับใด ๆ"
        />
      </div>

      {confirm.dialog}
    </>
  );
}

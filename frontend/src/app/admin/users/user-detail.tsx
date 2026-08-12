"use client";

/**
 * Slide-over detail + editor for one account on the admin roster.
 *
 * Reads `GET /admin/users/{id}/` and writes partial `PATCH` bodies with
 * only the keys that changed - the backend rejects unknown keys with 400
 * and refuses with 403 `protected_account` when the caller touches their
 * own access flags or any flag of a superuser. Those switches are
 * therefore disabled up front, and the refusal is still translated to a
 * clear toast if it slips through (e.g. a roster row went stale).
 */

import { useState } from "react";

import Link from "next/link";

import { api, type Paginated } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { AdminUser } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { relativeThai } from "@/lib/datetime";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  DetailPanel,
  DetailRow,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

/** The keys `PATCH /admin/users/{id}/` accepts - nothing else is sent. */
type UserPatch = Partial<{
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_staff: boolean;
  is_email_verified: boolean;
}>;

/** "ชื่อจริง นามสกุล", or null when the account never filled either in. */
export function fullName(user: AdminUser): string | null {
  const name = `${user.first_name} ${user.last_name}`.trim();
  return name || null;
}

/** The chip row every roster surface shares: status + role + email state. */
export function AccountBadges({ user }: { user: AdminUser }) {
  return (
    <>
      <Badge tone={user.is_active ? "success" : "danger"}>
        {user.is_active ? "ใช้งาน" : "ระงับ"}
      </Badge>
      {user.is_superuser ? (
        <Badge tone="berry">ผู้ดูแลสูงสุด</Badge>
      ) : user.is_staff ? (
        <Badge tone="lavender">สตาฟ</Badge>
      ) : null}
      <Badge tone={user.is_email_verified ? "mint" : "warning"}>
        {user.is_email_verified ? "ยืนยันอีเมลแล้ว" : "ยังไม่ยืนยัน"}
      </Badge>
    </>
  );
}

export function UserDetailPanel({
  userId,
  onClose,
  onChanged,
  onAdjustRewards,
}: {
  userId: number | null;
  onClose: () => void;
  /** The roster behind the panel must reflect every successful PATCH. */
  onChanged: () => void;
  /** Hands the username to the reward-adjustment panel below the roster. */
  onAdjustRewards: (username: string) => void;
}) {
  const { toast } = useToast();
  const confirm = useConfirm();
  // `OwnProfile` carries no numeric id, so "the caller's own row" is
  // matched by username - unique at the API level, so just as safe.
  const { user: caller } = useAuth();

  const detail = useApiQuery(
    (signal) =>
      userId !== null
        ? api.get<AdminUser>(`/admin/users/${userId}/`, { signal })
        : Promise.resolve(null),
    [userId],
  );

  // PATCH returns the fresh AdminUser; keeping it locally updates the
  // panel instantly without a second GET (the id guard drops it once
  // another row is opened).
  const [patched, setPatched] = useState<AdminUser | null>(null);
  const account = patched && patched.id === userId ? patched : detail.data;

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [saving, setSaving] = useState(false);

  // Seed the name inputs whenever a (new) account arrives from the GET -
  // done during render (the usePagedList trick), not in an effect.
  const [seededFrom, setSeededFrom] = useState<AdminUser | null>(null);
  if (detail.data && detail.data !== seededFrom) {
    setSeededFrom(detail.data);
    setFirstName(detail.data.first_name);
    setLastName(detail.data.last_name);
  }

  const namesDirty =
    account !== null &&
    (firstName !== account.first_name || lastName !== account.last_name);

  const isSelf = account !== null && caller?.username === account.username;
  // The backend protects the caller's own access flags and every flag of
  // a superuser; mirroring that here keeps the switches honest.
  const accessLocked = account !== null && (isSelf || account.is_superuser);
  const verifiedLocked = account !== null && account.is_superuser;

  async function save(body: UserPatch, message: string) {
    if (userId === null) return;
    setSaving(true);
    try {
      const updated = await api.patch<AdminUser>(`/admin/users/${userId}/`, {
        body,
      });
      setPatched(updated);
      onChanged();
      toast(message, "success");
    } catch (error) {
      if (error instanceof ApiError && error.code === "protected_account") {
        toast(
          "บัญชีนี้ได้รับการป้องกัน - ไม่สามารถแก้สิทธิ์ของตัวเองหรือผู้ดูแลสูงสุดได้",
          "danger",
        );
      } else {
        toast(describeAdminError(error), "danger");
      }
    } finally {
      setSaving(false);
    }
  }

  function saveNames() {
    if (!account || !namesDirty) return;
    // Send only the changed keys - a partial PATCH is the contract.
    const body: UserPatch = {};
    if (firstName !== account.first_name) body.first_name = firstName;
    if (lastName !== account.last_name) body.last_name = lastName;
    save(body, "บันทึกชื่อจริงแล้ว");
  }

  function toggleVerified(next: boolean) {
    save(
      { is_email_verified: next },
      next ? "ทำเครื่องหมายยืนยันอีเมลแล้ว" : "ยกเลิกการยืนยันอีเมลแล้ว",
    );
  }

  function toggleActive(next: boolean) {
    if (!account) return;
    if (next) {
      save({ is_active: true }, "เปิดใช้งานบัญชีแล้ว");
      return;
    }
    confirm.ask({
      title: "ระงับบัญชีนี้?",
      body: `@${account.username} จะเข้าสู่ระบบไม่ได้จนกว่าจะเปิดใช้งานอีกครั้ง เนื้อหาที่เคยสร้างยังอยู่ครบ`,
      confirmLabel: "ระงับบัญชี",
      danger: true,
      action: () => save({ is_active: false }, "ระงับบัญชีแล้ว"),
    });
  }

  function toggleStaff(next: boolean) {
    if (!account) return;
    confirm.ask({
      title: next ? "ให้สิทธิ์สตาฟ?" : "ถอนสิทธิ์สตาฟ?",
      body: next
        ? `@${account.username} จะเข้าหน้าแอดมินและจัดการเนื้อหาได้ทั้งระบบ`
        : `@${account.username} จะเข้าหน้าแอดมินไม่ได้อีกจนกว่าจะได้สิทธิ์คืน`,
      confirmLabel: next ? "ให้สิทธิ์สตาฟ" : "ถอนสิทธิ์",
      danger: !next,
      action: () =>
        save(
          { is_staff: next },
          next ? "ให้สิทธิ์สตาฟแล้ว" : "ถอนสิทธิ์สตาฟแล้ว",
        ),
    });
  }

  return (
    <>
      <DetailPanel
        open={userId !== null}
        title={
          account
            ? account.display_name || account.username
            : "รายละเอียดผู้ใช้"
        }
        onClose={onClose}
        footer={
          account ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onAdjustRewards(account.username)}
            >
              ปรับยอดคะแนนรางวัลให้ผู้ใช้นี้
            </Button>
          ) : null
        }
      >
        {detail.loading && !account ? (
          <p className="text-fg-muted">กำลังโหลด…</p>
        ) : detail.error ? (
          <ErrorState error={detail.error} onRetry={detail.refetch} />
        ) : account ? (
          <>
            <div className="flex items-center gap-3">
              <Avatar
                src={account.avatar_url}
                name={account.display_name || account.username}
                size="lg"
              />
              <div className="min-w-0">
                <p className="truncate font-medium text-fg">
                  {account.display_name || account.username}
                </p>
                <p className="font-mono text-xs text-fg-subtle">
                  @{account.username}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  <AccountBadges user={account} />
                </div>
              </div>
            </div>

            <dl className="mt-4">
              <DetailRow label="อีเมล">{account.email}</DetailRow>
              <DetailRow label="ชื่อจริง">
                {fullName(account) ?? "-"}
              </DetailRow>
              <DetailRow label="ระดับฝีมือ">
                {account.experience_level || "-"}
              </DetailRow>
              <DetailRow label="ยอมรับข้อตกลงเมื่อ">
                {account.terms_accepted_at
                  ? relativeThai(account.terms_accepted_at)
                  : "-"}
              </DetailRow>
              <DetailRow label="ยืนยันอีเมลเมื่อ">
                {account.email_verified_at
                  ? relativeThai(account.email_verified_at)
                  : "ยังไม่ยืนยัน"}
              </DetailRow>
              <DetailRow label="เข้าร่วมเมื่อ">
                {relativeThai(account.created_at)}
              </DetailRow>
              <DetailRow label="เข้าสู่ระบบล่าสุด">
                {account.last_login ? relativeThai(account.last_login) : "-"}
              </DetailRow>
              {account.deactivated_at ? (
                <DetailRow label="ระงับเมื่อ">
                  {relativeThai(account.deactivated_at)}
                </DetailRow>
              ) : null}
            </dl>

            <ActivitySummary account={account} />

            <EmailActions account={account} saving={saving} />

            <section className="mt-5">
              <h3 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
                แก้ไขชื่อจริง
              </h3>
              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                <Field label="ชื่อ">
                  {(control) => (
                    <Input
                      {...control}
                      value={firstName}
                      onChange={(event) => setFirstName(event.target.value)}
                    />
                  )}
                </Field>
                <Field label="นามสกุล">
                  {(control) => (
                    <Input
                      {...control}
                      value={lastName}
                      onChange={(event) => setLastName(event.target.value)}
                    />
                  )}
                </Field>
              </div>
              <Button
                size="sm"
                className="mt-3"
                disabled={!namesDirty}
                loading={saving && namesDirty}
                onClick={saveNames}
              >
                บันทึกชื่อ
              </Button>
            </section>

            <section className="mt-5 border-t border-edge pt-3">
              <h3 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
                สถานะบัญชีและสิทธิ์
              </h3>
              <div className="divide-y divide-edge/60">
                <Switch
                  checked={account.is_email_verified}
                  onChange={toggleVerified}
                  disabled={saving || verifiedLocked}
                  label="ยืนยันอีเมลแล้ว"
                  description="สำหรับกรณีฉุกเฉินที่อีเมลยืนยันส่งไม่ถึง - เปิดเพื่อยืนยันแทนผู้ใช้"
                />
                <Switch
                  checked={account.is_active}
                  onChange={toggleActive}
                  disabled={saving || accessLocked}
                  label="เปิดใช้งานบัญชี"
                  description="ปิดเพื่อระงับบัญชี - ผู้ใช้จะเข้าสู่ระบบไม่ได้จนกว่าจะเปิดคืน"
                />
                <Switch
                  checked={account.is_staff}
                  onChange={toggleStaff}
                  disabled={saving || accessLocked}
                  label="สิทธิ์สตาฟ"
                  description="เข้าหน้าแอดมินและจัดการเนื้อหาได้ทั้งระบบ"
                />
              </div>
              {accessLocked ? (
                <p className="mt-1 text-xs text-fg-subtle">
                  ไม่สามารถแก้สิทธิ์ของตัวเองหรือผู้ดูแลสูงสุดได้
                </p>
              ) : null}
            </section>
          </>
        ) : null}
      </DetailPanel>

      {confirm.dialog}
    </>
  );
}

/** One cross-surface count, fetched as `count` off a one-row page. */
function useActivityCount(path: string, query: Record<string, string>) {
  return useApiQuery<Paginated<unknown>>(
    (signal) =>
      api.get<Paginated<unknown>>(path, {
        query: { ...query, page_size: 1 },
        signal,
      }),
    [path, JSON.stringify(query)],
  );
}

/**
 * What this account has done across the platform - real counts only.
 * Courses / recipes / posts ride on the roster's own annotations;
 * reviews and certificates are one-row count fetches per surface.
 */
function ActivitySummary({ account }: { account: AdminUser }) {
  const username = account.username;
  const reviews = useActivityCount("/admin/reviews/", { username });
  const certificates = useActivityCount("/admin/certificates/", { username });

  const rows: Array<{
    label: string;
    count: number | undefined;
    loading: boolean;
    href:
      | "/admin/progress"
      | "/admin/recipes"
      | "/admin/posts"
      | "/admin/reviews"
      | "/admin/certificates";
  }> = [
    {
      label: "คอร์สที่เรียน",
      count: account.courses_count,
      loading: false,
      href: "/admin/progress",
    },
    {
      label: "สูตรที่สร้าง",
      count: account.recipes_count,
      loading: false,
      href: "/admin/recipes",
    },
    {
      label: "โพสต์ชุมชน",
      count: account.posts_count,
      loading: false,
      href: "/admin/posts",
    },
    {
      label: "รีวิวที่เขียน",
      count: reviews.data?.count,
      loading: reviews.loading,
      href: "/admin/reviews",
    },
    {
      label: "ใบประกาศที่ได้รับ",
      count: certificates.data?.count,
      loading: certificates.loading,
      href: "/admin/certificates",
    },
  ];

  return (
    <section className="mt-5">
      <h3 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
        กิจกรรมบนแพลตฟอร์ม
      </h3>
      <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {rows.map((row) => (
          <div
            key={row.label}
            className="rounded-lg border border-edge bg-surface px-3 py-2"
          >
            <dt className="text-[11px] text-fg-subtle">{row.label}</dt>
            <dd className="mt-0.5 font-mono text-lg tabular-nums text-fg">
              {row.loading ? "…" : (row.count ?? "-")}
            </dd>
            <Link
              href={row.href}
              className="text-[11px] text-accent hover:underline focus-visible:outline-2 focus-visible:outline-focus"
            >
              เปิดหน้าจัดการ →
            </Link>
          </div>
        ))}
      </dl>
    </section>
  );
}

/**
 * Staff-triggered account emails (ADR 0031): a password-reset link and
 * a verification resend. Eligibility mirrors the backend rules so the
 * buttons never promise an email the server would refuse.
 */
function EmailActions({
  account,
  saving,
}: {
  account: AdminUser;
  saving: boolean;
}) {
  const { toast } = useToast();
  const [sending, setSending] = useState<"reset" | "verify" | null>(null);

  async function send(kind: "reset" | "verify") {
    setSending(kind);
    try {
      await api.post(
        kind === "reset"
          ? `/admin/users/${account.id}/send-password-reset/`
          : `/admin/users/${account.id}/resend-verification/`,
      );
      toast(
        kind === "reset"
          ? `ส่งลิงก์รีเซ็ตรหัสผ่านไปที่อีเมลของ @${account.username} แล้ว`
          : `ส่งอีเมลยืนยันไปที่ @${account.username} อีกครั้งแล้ว`,
        "success",
      );
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setSending(null);
    }
  }

  return (
    <section className="mt-5 border-t border-edge pt-3">
      <h3 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
        อีเมลถึงผู้ใช้
      </h3>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="secondary"
          disabled={saving || sending !== null || !account.is_active}
          loading={sending === "reset"}
          onClick={() => void send("reset")}
        >
          ส่งลิงก์รีเซ็ตรหัสผ่าน
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={
            saving ||
            sending !== null ||
            !account.is_active ||
            account.is_email_verified
          }
          loading={sending === "verify"}
          onClick={() => void send("verify")}
        >
          ส่งอีเมลยืนยันอีกครั้ง
        </Button>
      </div>
      <p className="mt-1.5 text-xs text-fg-subtle">
        {!account.is_active
          ? "บัญชีที่ถูกระงับจะไม่ได้รับอีเมลใด ๆ"
          : account.is_email_verified
            ? "อีเมลนี้ยืนยันแล้ว - เหลือเฉพาะลิงก์รีเซ็ตรหัสผ่าน"
            : "ระบบส่งไปที่อีเมลที่ลงทะเบียนไว้เท่านั้น"}
      </p>
    </section>
  );
}

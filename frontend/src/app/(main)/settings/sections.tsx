"use client";

/**
 * The five settings panels.
 *
 * Every control here writes to a field that actually exists on
 * `PATCH /users/preferences/` or `PATCH /me/notifications/preferences/`.
 * Where the spec asked for something the backend has no column for, a
 * `NotAvailable` note names the gap instead of a control that pretends 
 * see the "unsupported" list in each panel's docstring.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { UserPreference } from "@/lib/api/models";
import { useAuth } from "@/lib/auth/auth-context";
import { useFormSubmit } from "@/lib/forms/use-form";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { PasswordInput } from "@/components/ui/password-input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import {
  CheckChips,
  Group,
  NotAvailable,
  RadioPills,
  Row,
  Rows,
  SaveIndicator,
} from "./primitives";
import { useAutoSave } from "./use-auto-save";

/* ------------------------------------------------------------------ */
/* Vocabulary  mirrors the backend enums exactly                      */
/* ------------------------------------------------------------------ */

const DIFFICULTY_OPTIONS = [
  { value: "beginner", label: "มือใหม่", hint: "อธิบายทุกขั้นตอนแบบละเอียด เหมาะกับคนเพิ่งเริ่มอบ" },
  { value: "intermediate", label: "ระดับกลาง", hint: "ข้ามพื้นฐาน เน้นเทคนิคและจุดที่มักพลาด" },
  { value: "advanced", label: "ขั้นสูง", hint: "สูตรและเทคนิคที่ต้องอาศัยประสบการณ์" },
  { value: "professional", label: "มืออาชีพ", hint: "ระดับร้าน  สัดส่วน อุณหภูมิ และการผลิตจำนวนมาก" },
] as const;

const DIET_OPTIONS = [
  { value: "vegan", label: "วีแกน" },
  { value: "vegetarian", label: "มังสวิรัติ" },
  { value: "gluten_free", label: "ไม่มีกลูเตน" },
  { value: "dairy_free", label: "ไม่มีนมวัว" },
  { value: "nut_free", label: "ไม่มีถั่ว" },
  { value: "egg_free", label: "ไม่มีไข่" },
] as const;

const VISIBILITY_OPTIONS = [
  { value: "public", label: "ทุกคน", hint: "ใครก็เปิดดูโปรไฟล์สาธารณะของคุณได้ รวมถึงคนที่ยังไม่ได้เข้าสู่ระบบ" },
  { value: "members", label: "เฉพาะสมาชิก", hint: "เฉพาะผู้ที่เข้าสู่ระบบ KawaiiBake แล้วเท่านั้น" },
  { value: "private", label: "เฉพาะฉัน", hint: "คนอื่นจะไม่พบโปรไฟล์ของคุณเลย" },
] as const;

const THEME_OPTIONS = [
  { value: "system", label: "ตามระบบ" },
  { value: "light", label: "สว่าง" },
  { value: "dark", label: "มืด" },
] as const;

const LOCALE_OPTIONS = [
  { value: "th", label: "ไทย" },
  { value: "en", label: "English" },
] as const;

const WEEKLY_GOALS = [0, 30, 60, 120, 180, 300, 600];

const NOTIFICATION_LABELS: Record<string, { label: string; description: string }> = {
  review_received: {
    label: "มีคนรีวิวผลงานของฉัน",
    description: "เมื่อมีผู้ใช้รีวิวสูตรหรือคอร์สที่คุณสร้าง",
  },
  course_enrollment: {
    label: "มีผู้เรียนใหม่ในคอร์สของฉัน",
    description: "เมื่อมีคนลงทะเบียนเรียนคอร์สที่คุณสอน",
  },
  achievement_earned: {
    label: "ได้รับเหรียญความสำเร็จ",
    description: "เมื่อคุณปลดล็อกความสำเร็จหรือได้รับใบประกาศนียบัตรใหม่",
  },
  qa_answer_received: {
    label: "มีคนตอบคำถามของฉัน",
    description: "เมื่อมีผู้ตอบคำถามที่คุณถามไว้ในบทเรียน",
  },
  qa_answer_accepted: {
    label: "คำตอบของฉันถูกเลือก",
    description: "เมื่อคำตอบของคุณถูกเลือกเป็นคำตอบที่ดีที่สุด",
  },
};

/* ================================================================== */
/* 1  การเรียนและการทำขนม                                            */
/* ================================================================== */

/**
 * Backed by `preferred_difficulty`, `dietary_restrictions` and
 * `weekly_goal_minutes` on `UserPreference`.
 *
 * Not built, because no column exists: measurement units (metric vs
 * imperial) and learning style (step-by-step / concise / video-first).
 */
export function LearningPanel({
  preferences,
}: {
  preferences: UserPreference;
}) {
  const save = useAutoSave(preferences, "/users/preferences/");
  const diets = (save.value.dietary_restrictions ?? []).filter(
    (item) => item !== "none",
  );

  function toggleDiet(value: string, next: boolean) {
    const updated = next
      ? [...diets, value]
      : diets.filter((item) => item !== value);
    // "none" is the backend's explicit empty marker, so an empty
    // selection is sent as ["none"] rather than [].
    save.update({ dietary_restrictions: updated.length ? updated : ["none"] });
  }

  return (
    <div className="space-y-8">
      <Group
        title="ระดับคำแนะนำ"
        description="กำหนดความละเอียดของคำแนะนำและเคล็ดลับที่ KawaiiBake แสดงให้คุณ"
      >
        <RadioPills
          legend="ระดับที่ต้องการ"
          value={save.value.preferred_difficulty as (typeof DIFFICULTY_OPTIONS)[number]["value"]}
          options={[...DIFFICULTY_OPTIONS]}
          onChange={(value) => save.update({ preferred_difficulty: value })}
        />
      </Group>

      <Group
        title="ข้อจำกัดด้านอาหาร"
        description="ใช้ปรับคำแนะนำและการค้นหาให้ตรงกับที่คุณกินได้"
        footnote={
          <>
            <strong className="font-medium text-fg-muted">
              นี่คือตัวกรองความชอบ ไม่ใช่การรับรองความปลอดภัย
            </strong>{" "}
             KawaiiBake ยังไม่มีข้อมูลสารก่อภูมิแพ้ที่ตรวจสอบแล้วในระดับวัตถุดิบ
            กรุณาอ่านส่วนผสมทุกครั้งก่อนทำหากคุณแพ้อาหาร
          </>
        }
      >
        <CheckChips
          legend="เลือกได้มากกว่าหนึ่งข้อ"
          values={diets}
          options={[...DIET_OPTIONS]}
          onToggle={toggleDiet}
        />
      </Group>

      <Group
        title="เป้าหมายการเรียนต่อสัปดาห์"
        description="ใช้วัดความคืบหน้าของคุณเอง ไม่มีการแจ้งเตือนบังคับ"
      >
        <Rows>
          <Row label="เวลาที่ตั้งเป้าไว้" htmlFor="weekly-goal">
            <Select
              id="weekly-goal"
              value={String(save.value.weekly_goal_minutes)}
              onChange={(event) =>
                save.update({ weekly_goal_minutes: Number(event.target.value) })
              }
            >
              {WEEKLY_GOALS.map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes === 0
                    ? "ไม่ตั้งเป้าหมาย"
                    : minutes < 60
                      ? `${minutes} นาที / สัปดาห์`
                      : `${minutes / 60} ชั่วโมง / สัปดาห์`}
                </option>
              ))}
            </Select>
          </Row>
        </Rows>
      </Group>

      <NotAvailable
        title="หน่วยวัด และรูปแบบการเรียน ยังไม่เปิดให้ตั้งค่า"
        reason="ระบบหลังบ้านยังไม่มีที่เก็บค่าเหล่านี้ (metric/imperial และรูปแบบคำอธิบาย) เราจึงยังไม่ใส่ปุ่มที่กดแล้วไม่ถูกบันทึกจริง"
      />

      <SaveIndicator status={save.status} error={save.error} />
    </div>
  );
}

/* ================================================================== */
/* 2  การแจ้งเตือน                                                    */
/* ================================================================== */

/**
 * Two owners, two endpoints: the e-mail switches live on
 * `UserPreference`, the per-event in-app switches belong to the
 * notifications domain and are written through its own endpoint. They
 * are shown together because that is how a person thinks about them,
 * but nothing is duplicated or re-implemented on this side.
 */
export function NotificationsPanel({
  preferences,
  notifications,
}: {
  preferences: UserPreference;
  notifications: Record<string, boolean>;
}) {
  const emails = useAutoSave(preferences, "/users/preferences/");
  const inApp = useAutoSave(notifications, "/me/notifications/preferences/");

  return (
    <div className="space-y-8">
      <Group
        title="อีเมล"
        description="อีเมลที่ KawaiiBake จะส่งถึงคุณ"
      >
        <Rows>
          <Switch
            label="ความเคลื่อนไหวของคอร์ส"
            description="บทเรียนใหม่ การอัปเดตคอร์สที่คุณลงทะเบียนไว้"
            checked={emails.value.email_course_updates}
            onChange={(next) => emails.update({ email_course_updates: next })}
          />
          <Switch
            label="อัปเดตฟีเจอร์ใหม่"
            description="ความเปลี่ยนแปลงของระบบและฟีเจอร์ที่เพิ่มเข้ามา"
            checked={emails.value.email_product_updates}
            onChange={(next) => emails.update({ email_product_updates: next })}
          />
          <Switch
            label="ข่าวสารและโปรโมชัน"
            description="เนื้อหาแนะนำและกิจกรรมเป็นครั้งคราว ปิดได้ตลอดเวลา"
            checked={emails.value.email_marketing}
            onChange={(next) => emails.update({ email_marketing: next })}
          />
        </Rows>
      </Group>

      <Group
        title="การแจ้งเตือนในแอป"
        description="กระดิ่งแจ้งเตือนด้านบนขวา เลือกได้ว่าจะให้เรื่องไหนเข้ามาบ้าง"
      >
        <Rows>
          {Object.entries(inApp.value).map(([event, enabled]) => {
            const copy = NOTIFICATION_LABELS[event];
            return (
              <Switch
                key={event}
                label={copy?.label ?? event}
                description={copy?.description}
                checked={enabled}
                onChange={(next) => inApp.update({ [event]: next })}
              />
            );
          })}
        </Rows>
      </Group>

      <SaveIndicator
        status={inApp.status === "idle" ? emails.status : inApp.status}
        error={inApp.error ?? emails.error}
      />
    </div>
  );
}

/* ================================================================== */
/* 3  ความเป็นส่วนตัว                                                 */
/* ================================================================== */

/**
 * Backed by `profile_visibility`, `show_birthday` and `show_location`.
 * These are enforced server-side  the public profile endpoint redacts
 * before serialising  so the controls describe a real boundary rather
 * than a client-side courtesy.
 *
 * Not built: per-surface visibility for community posts, saved content
 * and learning progress. No column, and inventing one on this side
 * would advertise a protection nothing enforces.
 */
export function PrivacyPanel({ preferences }: { preferences: UserPreference }) {
  const save = useAutoSave(preferences, "/users/preferences/");

  return (
    <div className="space-y-8">
      <Group
        title="โปรไฟล์สาธารณะ"
        description="กำหนดว่าใครเปิดดูโปรไฟล์ของคุณได้บ้าง มีผลกับข้อมูลที่คุณเลือกเผยแพร่เท่านั้น"
      >
        <RadioPills
          legend="ใครดูโปรไฟล์ของฉันได้"
          value={save.value.profile_visibility as (typeof VISIBILITY_OPTIONS)[number]["value"]}
          options={[...VISIBILITY_OPTIONS]}
          onChange={(value) => save.update({ profile_visibility: value })}
        />
      </Group>

      <Group
        title="ข้อมูลที่แสดงบนโปรไฟล์"
        description="เลือกได้ว่าจะเปิดเผยข้อมูลส่วนตัวบางอย่างหรือไม่ แม้โปรไฟล์จะเปิดสาธารณะ"
        footnote="อีเมลของคุณไม่เคยแสดงบนโปรไฟล์สาธารณะไม่ว่าจะตั้งค่าแบบใด"
      >
        <Rows>
          <Switch
            label="แสดงวันเกิด"
            description="ให้คนอื่นเห็นวันเกิดที่คุณกรอกไว้ในโปรไฟล์"
            checked={save.value.show_birthday}
            onChange={(next) => save.update({ show_birthday: next })}
          />
          <Switch
            label="แสดงที่อยู่"
            description="ให้คนอื่นเห็นเมืองหรือจังหวัดที่คุณระบุไว้"
            checked={save.value.show_location}
            onChange={(next) => save.update({ show_location: next })}
          />
        </Rows>
      </Group>

      <NotAvailable
        title="การซ่อนโพสต์ รายการที่บันทึก และความคืบหน้าแยกรายการ ยังไม่เปิดให้ตั้งค่า"
        reason="ระบบหลังบ้านยังไม่มีการควบคุมระดับนี้ เราจึงไม่แสดงสวิตช์ที่ดูเหมือนปกป้องข้อมูลได้ทั้งที่ยังบังคับใช้ไม่ได้"
      />

      <SaveIndicator status={save.status} error={save.error} />
    </div>
  );
}

/* ================================================================== */
/* 4  การแสดงผล                                                       */
/* ================================================================== */

/**
 * `theme` and `locale` are real, validated columns and this panel does
 * persist them. What it must not do is imply they already change the
 * screen: the interface ships light-only (there is no dark palette in
 * `tokens.css` and no `dark:` variant anywhere), and the UI copy is
 * Thai-only. `locale` does have a live consumer  the assistant starts
 * a conversation in it  so that one is described by what it actually
 * does today.
 *
 * Not built: interface density and kitchen mode. Both would be
 * device-local state with nowhere to persist, and the Screen Wake Lock
 * API is unavailable across the browsers this app targets.
 */
export function AppearancePanel({
  preferences,
}: {
  preferences: UserPreference;
}) {
  const save = useAutoSave(preferences, "/users/preferences/");

  return (
    <div className="space-y-8">
      <Group
        title="ธีม"
        description="บันทึกไว้กับบัญชีของคุณ พร้อมใช้เมื่อโหมดมืดเปิดให้ใช้งาน"
        footnote="ตอนนี้ KawaiiBake ยังแสดงผลเป็นธีมสว่างอย่างเดียว ค่าที่เลือกไว้จะถูกบันทึกและนำมาใช้ทันทีที่โหมดมืดพร้อม"
      >
        <RadioPills
          legend="ธีมที่ต้องการ"
          value={save.value.theme as (typeof THEME_OPTIONS)[number]["value"]}
          options={[...THEME_OPTIONS]}
          onChange={(value) => save.update({ theme: value })}
        />
      </Group>

      <Group
        title="ภาษา"
        description="ภาษาที่ผู้ช่วย AI ใช้ตอบคุณเป็นค่าเริ่มต้น"
        footnote="หน้าจอของ KawaiiBake ยังเป็นภาษาไทยทั้งหมด การตั้งค่านี้มีผลกับบทสนทนาของผู้ช่วย AI"
      >
        <RadioPills
          legend="ภาษาที่ต้องการ"
          value={save.value.locale as (typeof LOCALE_OPTIONS)[number]["value"]}
          options={[...LOCALE_OPTIONS]}
          onChange={(value) => save.update({ locale: value })}
        />
      </Group>

      <NotAvailable
        title="ความหนาแน่นของหน้าจอ และโหมดครัว ยังไม่เปิดให้ตั้งค่า"
        reason="ทั้งสองอย่างยังไม่มีที่เก็บค่าในระบบหลังบ้าน และการกันหน้าจอดับยังใช้ไม่ได้ในเบราว์เซอร์ที่รองรับอยู่"
      />

      <SaveIndicator status={save.status} error={save.error} />
    </div>
  );
}

/* ================================================================== */
/* 5  บัญชีและความปลอดภัย                                             */
/* ================================================================== */

function ChangePasswordDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const form = useFormSubmit();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const ok = await form.submit(async () => {
      await api.post("/auth/password-change/", {
        body: { current_password: current, new_password: next },
      });
    });
    if (ok) {
      toast("เปลี่ยนรหัสผ่านแล้ว", "success");
      setCurrent("");
      setNext("");
      onClose();
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="เปลี่ยนรหัสผ่าน">
      <form onSubmit={submit} className="space-y-4">
        {form.formError ? (
          <p
            role="alert"
            className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger"
          >
            {form.formError}
          </p>
        ) : null}
        <Field label="รหัสผ่านปัจจุบัน" errors={form.fieldErrors.current_password}>
          {(control) => (
            <PasswordInput
              {...control}
              value={current}
              autoComplete="current-password"
              onChange={(event) => setCurrent(event.target.value)}
            />
          )}
        </Field>
        <Field label="รหัสผ่านใหม่" errors={form.fieldErrors.new_password}>
          {(control) => (
            <PasswordInput
              {...control}
              value={next}
              autoComplete="new-password"
              onChange={(event) => setNext(event.target.value)}
            />
          )}
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            ยกเลิก
          </Button>
          <Button type="submit" loading={form.submitting}>
            บันทึกรหัสผ่านใหม่
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function DeactivateDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const router = useRouter();
  const { refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  // Typing the word is the second step: a destructive action must never
  // be reachable by one stray click on a button labelled in red.
  const [confirmation, setConfirmation] = useState("");
  const REQUIRED = "ปิดใช้งาน";

  async function deactivate() {
    setBusy(true);
    try {
      await api.post("/users/account/deactivate/");
      // The server has already dropped the session. Re-reading it flips
      // the app to anonymous, so no stale identity survives the redirect.
      await refresh();
      router.replace("/");
    } catch (error) {
      toast(
        error instanceof ApiError ? error.message : "ปิดใช้งานบัญชีไม่สำเร็จ",
        "danger",
      );
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="ปิดใช้งานบัญชี">
      <div className="space-y-4">
        <p className="text-sm leading-relaxed text-fg">
          บัญชีของคุณจะถูกปิดใช้งานและคุณจะออกจากระบบทันที
          โปรไฟล์สาธารณะจะไม่แสดงอีกต่อไป
        </p>
        <p className="text-sm leading-relaxed text-fg-muted">
          สูตร คอร์ส และความคืบหน้าของคุณจะยังถูกเก็บไว้
          หากต้องการกลับมาใช้งาน กรุณาติดต่อผู้ดูแลระบบ
        </p>
        <Field
          label={`พิมพ์ “${REQUIRED}” เพื่อยืนยัน`}
        >
          {(control) => (
            <input
              {...control}
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              autoComplete="off"
              className="block w-full rounded-control border border-edge-strong/50 bg-surface px-3.5 py-2.5 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus"
            />
          )}
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            ยกเลิก
          </Button>
          <Button
            variant="danger"
            loading={busy}
            disabled={confirmation !== REQUIRED}
            onClick={() => void deactivate()}
          >
            ปิดใช้งานบัญชีของฉัน
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/**
 * Password change and deactivation are both real endpoints.
 *
 * Not built: active-session management and permanent account deletion.
 * Neither exists on the backend, and a "delete account" button that only
 * deactivates would be a lie about something irreversible.
 */
export function AccountPanel({
  email,
  isEmailVerified,
}: {
  email: string;
  isEmailVerified: boolean;
}) {
  const [changingPassword, setChangingPassword] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const { user } = useAuth();

  return (
    <div className="space-y-8">
      <Group title="บัญชี" description="ข้อมูลที่ใช้เข้าสู่ระบบ">
        <Rows>
          <Row label="อีเมล" description={email}>
            {isEmailVerified ? (
              <span className="flex items-center gap-1.5 text-sm text-success">
                <Icon name="ui/check-circle" tint className="size-4" />
                ยืนยันแล้ว
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-sm text-warning">
                <Icon name="ui/alert" tint className="size-4" />
                ยังไม่ยืนยัน
              </span>
            )}
          </Row>
          <Row label="ชื่อผู้ใช้" description={`@${user?.username ?? ""}`}>
            <span className="text-sm text-fg-subtle">เปลี่ยนไม่ได้</span>
          </Row>
        </Rows>
      </Group>

      <Group title="ความปลอดภัย" description="รหัสผ่านสำหรับเข้าสู่ระบบ">
        <Rows>
          <Row
            label="รหัสผ่าน"
            description="แนะนำให้เปลี่ยนเป็นระยะ และไม่ใช้ซ้ำกับเว็บอื่น"
          >
            <Button variant="secondary" onClick={() => setChangingPassword(true)}>
              เปลี่ยนรหัสผ่าน
            </Button>
          </Row>
        </Rows>
      </Group>

      <Group
        title="ปิดใช้งานบัญชี"
        description="หยุดใช้งาน KawaiiBake ชั่วคราว โดยข้อมูลของคุณยังอยู่"
      >
        <Rows>
          <Row
            label="ปิดใช้งานบัญชีของฉัน"
            description="คุณจะออกจากระบบทันที และโปรไฟล์จะไม่แสดงต่อผู้อื่น"
          >
            <Button variant="danger" onClick={() => setDeactivating(true)}>
              ปิดใช้งานบัญชี
            </Button>
          </Row>
        </Rows>
      </Group>

      <NotAvailable
        title="การจัดการอุปกรณ์ที่เข้าสู่ระบบ และการลบบัญชีถาวร ยังไม่เปิดให้ใช้งาน"
        reason="ระบบหลังบ้านยังไม่มีปลายทางสำหรับสองเรื่องนี้ การใส่ปุ่ม “ลบบัญชี” ที่จริง ๆ แล้วแค่ปิดใช้งาน จะเป็นการบอกข้อมูลผิดในเรื่องที่ย้อนกลับไม่ได้"
      />

      <p className="text-xs leading-relaxed text-fg-subtle">
        ต้องการแก้ชื่อที่แสดง รูปโปรไฟล์ หรือคำแนะนำตัว?{" "}
        <Link
          href="/profile"
          className="font-medium text-accent underline underline-offset-2 hover:text-accent-hover"
        >
          ไปที่โปรไฟล์ของฉัน
        </Link>
      </p>

      <ChangePasswordDialog
        open={changingPassword}
        onClose={() => setChangingPassword(false)}
      />
      <DeactivateDialog
        open={deactivating}
        onClose={() => setDeactivating(false)}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Profile shortcut  deliberately a link, never a form                */
/* ------------------------------------------------------------------ */

export function ProfileShortcut({
  displayName,
  username,
}: {
  displayName: string;
  username: string;
}) {
  return (
    <Card className="mb-8">
      <CardBody className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-berry-soft">
            <Icon name="ui/user" tint className="size-5 text-berry-ink" />
          </span>
          <div className="min-w-0">
            <p className="font-display text-base font-medium text-fg">
              โปรไฟล์ของฉัน
            </p>
            <p className="text-sm text-fg-muted">
              จัดการข้อมูลที่แสดงให้คนอื่นเห็น  {displayName || `@${username}`}
            </p>
          </div>
        </div>
        <Link href="/profile" className="shrink-0">
          <Button variant="secondary">
            แก้ไขโปรไฟล์
            <Icon name="ui/arrow-right" tint className="size-4" />
          </Button>
        </Link>
      </CardBody>
    </Card>
  );
}

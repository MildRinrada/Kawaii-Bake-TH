"use client";

/**
 * The notification composer: type → content → audience → delivery, with
 * a live preview that renders exactly what the notification center
 * will.
 *
 * Modes (via query params, resolved by the server wrapper):
 * - fresh compose (optionally `?kind=` preselecting a type)
 * - `?edit=` - edit a draft/scheduled campaign in place
 * - `?from=` - duplicate any campaign into a new draft
 * - `?template=` - start from a reusable template
 *
 * Delivery honesty: "ส่งตอนนี้" always confirms with the server's own
 * recipient estimate; scheduling stores a future timestamp the
 * dispatcher (Celery beat / `dispatch_campaigns`) fires on; variables
 * the audience cannot resolve block sending client-side with the same
 * rule the backend enforces (it re-checks anyway).
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type {
  AudienceEstimate,
  BroadcastResult,
  CourseListItem,
  NotificationCampaign,
  NotificationTemplateItem,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import { AdminPanel, SearchInput, useConfirm } from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";
import { cn } from "@/lib/cn";

import {
  ANNOUNCEMENT_KIND_OPTIONS,
  AUDIENCE_KINDS,
  DEFAULT_KIND,
  SKILL_LEVELS,
  isKnownKind,
  VARIABLES,
  type AudienceDoc,
  unresolvableIn,
} from "../kinds";
import { NotificationPreviewCard } from "../preview-card";

type DeliveryMode = "now" | "schedule" | "draft";

/** The card's own limits - mirrors the backend constants by the same
    name (CAMPAIGN_TITLE_MAX_LENGTH / CAMPAIGN_BODY_MAX_LENGTH). */
const TITLE_LIMIT = 60;
const BODY_LIMIT = 120;

/** In-app destinations an announcement may point at. Free text stays
    available for one specific recipe or course. */
const DESTINATIONS = [
  { href: "/recipes", label: "สูตรขนมทั้งหมด" },
  { href: "/courses", label: "คอร์สเรียนทั้งหมด" },
  { href: "/community", label: "ชุมชน" },
  { href: "/threads", label: "กระทู้ถาม-ตอบ" },
  { href: "/recommendations", label: "แนะนำสำหรับคุณ" },
  { href: "/achievements", label: "ความสำเร็จ" },
  { href: "/support", label: "ศูนย์ช่วยเหลือ" },
] as const;

/** Whole days between an ISO timestamp and now. Client-only, like the
    rest of this screen  the clock is never read on the server. */
function wholeDaysSince(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

function CharCount({ value, limit }: { value: string; limit: number }) {
  const used = value.length;
  return (
    <p
      className={cn(
        "mt-1 text-right text-xs tabular-nums",
        used >= limit ? "text-warning" : "text-fg-subtle",
      )}
    >
      {used}/{limit}
    </p>
  );
}

export function Composer({
  editId,
  fromId,
  templateId,
  presetKind,
}: {
  editId?: string;
  fromId?: string;
  templateId?: string;
  presetKind?: string;
}) {
  const router = useRouter();
  const { toast } = useToast();
  const confirm = useConfirm();

  const editing = editId !== undefined;
  const sourceId = editId ?? fromId;

  // ---- Source loading (edit / duplicate / template) -----------------
  const sourceCampaign = useApiQuery(
    (signal) =>
      sourceId
        ? api.get<NotificationCampaign>(
            `/admin/notifications/campaigns/${sourceId}/`,
            { signal },
          )
        : Promise.resolve(null),
    [sourceId],
  );
  const templateList = useApiQuery(
    (signal) =>
      templateId
        ? api.get<NotificationTemplateItem[]>(
            "/admin/notifications/templates/",
            { signal },
          )
        : Promise.resolve(null),
    [templateId],
  );

  // How recently the last announcement went out. Notification fatigue is
  // the main reason people switch notifications off entirely, so the
  // composer says it out loud rather than leaving the sender to guess.
  const recentSends = useApiQuery(
    (signal) =>
      api.get<Paginated<NotificationCampaign>>(
        "/admin/notifications/campaigns/",
        { query: { status: "sent", page_size: 1 }, signal },
      ),
    [],
  );
  const lastSentAt = recentSends.data?.results[0]?.sent_at ?? null;
  const daysSinceLastSend = lastSentAt ? wholeDaysSince(lastSentAt) : null;

  // ---- Form state ---------------------------------------------------
  const initialKind =
    presetKind && isKnownKind(presetKind) ? presetKind : DEFAULT_KIND;
  const [kind, setKind] = useState(initialKind);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [ctaText, setCtaText] = useState("");
  const [link, setLink] = useState("");

  const [audKind, setAudKind] = useState("all");
  const [days, setDays] = useState("30");
  const [courseSlug, setCourseSlug] = useState("");
  const [courseTitle, setCourseTitle] = useState("");
  const [level, setLevel] = useState("beginner");
  const [usernamesText, setUsernamesText] = useState("");

  const [mode, setMode] = useState<DeliveryMode>("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [compactPreview, setCompactPreview] = useState(false);
  // Editing an already-sent campaign: content only - saving amends the
  // delivered snapshots in every recipient's inbox (ADR 0030 amendment).
  const [sentLocked, setSentLocked] = useState(false);
  const [sentRecipients, setSentRecipients] = useState(0);

  // Seed once from the loaded source - the render-time pattern, so no
  // setState-in-effect.
  const [seededFrom, setSeededFrom] = useState<string | null>(null);
  const sourceKey = sourceId
    ? `campaign-${sourceId}`
    : templateId
      ? `template-${templateId}`
      : null;
  if (sourceKey && seededFrom !== sourceKey) {
    const campaign = sourceCampaign.data;
    const template = templateId
      ? (templateList.data ?? []).find(
          (item) => String(item.id) === templateId,
        )
      : null;
    const source = campaign ?? template;
    if (source) {
      setSeededFrom(sourceKey);
      setKind(isKnownKind(source.kind) ? source.kind : DEFAULT_KIND);
      setTitle(source.title);
      setBody(source.body);
      setCtaText(source.cta_text);
      setLink(source.link);
      if (campaign) {
        const audience = (campaign.audience ?? {}) as AudienceDoc;
        setAudKind(audience.kind ?? "all");
        if (audience.days !== undefined) setDays(String(audience.days));
        if (audience.course_slug) {
          setCourseSlug(audience.course_slug);
          setCourseTitle(audience.course_slug);
        }
        if (audience.level) setLevel(audience.level);
        if (audience.usernames) setUsernamesText(audience.usernames.join(", "));
        if (editing && campaign.status === "sent") {
          setSentLocked(true);
          setSentRecipients(campaign.recipients_count ?? 0);
        } else if (editing && campaign.status === "scheduled") {
          setMode("schedule");
          if (campaign.scheduled_at) {
            const at = new Date(campaign.scheduled_at);
            const pad = (value: number) => String(value).padStart(2, "0");
            setScheduledAt(
              `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`,
            );
          }
        } else if (editing) {
          setMode("draft");
        }
      }
    }
  }

  // ---- Course picker (course-scoped audiences) ----------------------
  const [courseSearch, setCourseSearch] = useState("");
  const debouncedCourseSearch = useDebounced(courseSearch);
  const courseScoped =
    audKind === "course_enrolled" || audKind === "course_completed";
  const courses = usePagedList<CourseListItem>("/courses/", {
    scope: courseScoped ? "all" : undefined,
    ordering: courseScoped ? "title" : undefined,
    search: courseScoped ? debouncedCourseSearch || undefined : undefined,
  });

  // ---- Audience document + estimate ---------------------------------
  function audienceDoc(): AudienceDoc | null {
    switch (audKind) {
      case "active":
      case "new_users": {
        const parsed = Number(days);
        if (!Number.isInteger(parsed) || parsed < 1 || parsed > 365) {
          return null;
        }
        return { kind: audKind, days: parsed };
      }
      case "course_enrolled":
      case "course_completed":
        return courseSlug ? { kind: audKind, course_slug: courseSlug } : null;
      case "skill_level":
        return { kind: audKind, level };
      case "specific_users": {
        const usernames = usernamesText
          .split(/[\s,]+/)
          .map((name) => name.trim())
          .filter(Boolean);
        return usernames.length > 0
          ? { kind: audKind, usernames }
          : null;
      }
      default:
        return { kind: audKind };
    }
  }

  const doc = audienceDoc();
  const docJson = doc ? JSON.stringify(doc) : null;
  const [estimate, setEstimate] = useState<{
    forDoc: string | null;
    count: number | null;
    error: string | null;
    loading: boolean;
  }>({ forDoc: null, count: null, error: null, loading: false });

  useEffect(() => {
    if (!docJson || sentLocked) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setEstimate((state) => ({ ...state, loading: true }));
      try {
        const result = await api.post<AudienceEstimate>(
          "/admin/notifications/audience/estimate/",
          { body: { audience: JSON.parse(docJson) }, signal: controller.signal },
        );
        setEstimate({
          forDoc: docJson,
          count: result.count,
          error: null,
          loading: false,
        });
      } catch (error) {
        if (controller.signal.aborted) return;
        setEstimate({
          forDoc: docJson,
          count: null,
          error:
            error instanceof ApiError && error.code === "invalid_audience"
              ? error.message
              : "ประเมินจำนวนผู้รับไม่สำเร็จ",
          loading: false,
        });
      }
    }, 500);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [docJson, sentLocked]);

  // ---- Variables ----------------------------------------------------
  const titleRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const [lastFocus, setLastFocus] = useState<"title" | "body">("body");

  function insertVariable(name: string) {
    const token = `{{${name}}}`;
    const target = lastFocus === "title" ? titleRef.current : bodyRef.current;
    const setter = lastFocus === "title" ? setTitle : setBody;
    const value = lastFocus === "title" ? title : body;
    const at = target?.selectionStart ?? value.length;
    setter(value.slice(0, at) + token + value.slice(at));
  }

  const blocked = unresolvableIn(`${title} ${body}`, audKind);

  // ---- Persist ------------------------------------------------------
  function buildPayload(status: "draft" | "scheduled", scheduledIso?: string) {
    return {
      kind,
      title: title.trim(),
      body: body.trim(),
      cta_text: ctaText.trim(),
      link: link.trim(),
      audience: doc,
      status,
      ...(scheduledIso ? { scheduled_at: scheduledIso } : {}),
    };
  }

  async function persist(
    status: "draft" | "scheduled",
    scheduledIso?: string,
  ): Promise<NotificationCampaign> {
    const payload = buildPayload(status, scheduledIso);
    if (editing) {
      return api.patch<NotificationCampaign>(
        `/admin/notifications/campaigns/${editId}/`,
        { body: payload },
      );
    }
    return api.post<NotificationCampaign>("/admin/notifications/campaigns/", {
      body: payload,
    });
  }

  function validateCommon(): boolean {
    if (!title.trim()) {
      setFieldError("กรุณากรอกหัวข้อการแจ้งเตือน");
      return false;
    }
    if (!doc) {
      setFieldError("กรุณากำหนดกลุ่มเป้าหมายให้ครบถ้วน");
      return false;
    }
    if (!link.trim()) {
      setFieldError(
        "กรุณาเลือกลิงก์ปลายทาง  ประกาศที่กดแล้วไม่พาไปไหนคือประกาศที่ผู้ใช้ทำอะไรต่อไม่ได้",
      );
      return false;
    }
    setFieldError(null);
    return true;
  }

  async function saveDraft() {
    if (!validateCommon()) return;
    setBusy(true);
    try {
      await persist("draft");
      toast("บันทึกฉบับร่างแล้ว", "success");
      router.push("/admin/notifications");
    } catch (error) {
      toast(describeAdminError(error), "danger");
      setBusy(false);
    }
  }

  async function schedule() {
    if (!validateCommon()) return;
    if (!scheduledAt || new Date(scheduledAt) <= new Date()) {
      setFieldError("กรุณาเลือกเวลาส่งในอนาคต");
      return;
    }
    if (blocked.length > 0) {
      setFieldError(
        `ตัวแปรเหล่านี้ใช้กับกลุ่มเป้าหมายนี้ไม่ได้: ${blocked.map((name) => `{{${name}}}`).join(", ")}`,
      );
      return;
    }
    setBusy(true);
    try {
      await persist("scheduled", new Date(scheduledAt).toISOString());
      toast("ตั้งเวลาส่งแล้ว", "success");
      router.push("/admin/notifications");
    } catch (error) {
      toast(describeAdminError(error), "danger");
      setBusy(false);
    }
  }

  function amendSent() {
    if (!title.trim()) {
      setFieldError("กรุณากรอกหัวข้อการแจ้งเตือน");
      return;
    }
    if (blocked.length > 0) {
      setFieldError(
        `ตัวแปรเหล่านี้ใช้กับกลุ่มเป้าหมายนี้ไม่ได้: ${blocked.map((name) => `{{${name}}}`).join(", ")}`,
      );
      return;
    }
    setFieldError(null);
    confirm.ask({
      title: "อัปเดตการแจ้งเตือนที่ส่งแล้ว?",
      body: `ข้อความใหม่จะแทนที่ของเดิมในกล่องแจ้งเตือนของผู้รับทั้ง ${sentRecipients.toLocaleString("th-TH")} บัญชีทันที`,
      confirmLabel: "บันทึกและอัปเดตผู้รับ",
      action: async () => {
        setBusy(true);
        try {
          await api.patch(`/admin/notifications/campaigns/${editId}/`, {
            body: {
              kind,
              title: title.trim(),
              body: body.trim(),
              cta_text: ctaText.trim(),
              link: link.trim(),
            },
          });
          toast("อัปเดตเนื้อหาถึงผู้รับแล้ว", "success");
          router.push("/admin/notifications");
        } catch (error) {
          toast(describeAdminError(error), "danger");
          setBusy(false);
        }
      },
    });
  }

  function sendNow() {
    if (!validateCommon()) return;
    if (blocked.length > 0) {
      setFieldError(
        `ตัวแปรเหล่านี้ใช้กับกลุ่มเป้าหมายนี้ไม่ได้: ${blocked.map((name) => `{{${name}}}`).join(", ")}`,
      );
      return;
    }
    const count = estimate.forDoc === docJson ? estimate.count : null;
    confirm.ask({
      title: "ส่งการแจ้งเตือนตอนนี้?",
      body:
        count === null
          ? "ระบบจะตรวจสอบกลุ่มเป้าหมายอีกครั้งตอนส่ง - ส่งแล้วเรียกคืนไม่ได้"
          : `การแจ้งเตือนจะถูกส่งถึงประมาณ ${count.toLocaleString("th-TH")} บัญชี - ส่งแล้วเรียกคืนไม่ได้`,
      confirmLabel: "ส่งตอนนี้",
      action: async () => {
        setBusy(true);
        try {
          const campaign = await persist("draft");
          const result = await api.post<BroadcastResult>(
            `/admin/notifications/campaigns/${campaign.id}/send/`,
          );
          toast(`ส่งถึง ${result.recipients} บัญชีแล้ว`, "success");
          router.push("/admin/notifications");
        } catch (error) {
          toast(describeAdminError(error), "danger");
          setBusy(false);
        }
      },
    });
  }

  // ---- Render -------------------------------------------------------
  if (sourceId && sourceCampaign.error) {
    return (
      <ErrorState error={sourceCampaign.error} onRetry={sourceCampaign.refetch} />
    );
  }
  const waitingForSource = Boolean(
    (sourceId && !sourceCampaign.data) ||
      (templateId && !templateList.data),
  );
  if (waitingForSource) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-10 w-64 rounded-md" />
        <Skeleton className="h-64 w-full rounded-md" />
      </div>
    );
  }

  return (
    <>
      <AdminPageHeader
        title={
          sentLocked
            ? "แก้ไขการแจ้งเตือนที่ส่งแล้ว"
            : editing
              ? "แก้ไขการแจ้งเตือน"
              : "สร้างการแจ้งเตือน"
        }
        description={
          sentLocked
            ? "แก้ได้เฉพาะเนื้อหา - บันทึกแล้วข้อความในกล่องแจ้งเตือนของผู้รับทุกคนจะอัปเดตทันที"
            : "เลือกประเภท เขียนเนื้อหา กำหนดกลุ่มเป้าหมาย แล้วส่งทันที ตั้งเวลา หรือเก็บเป็นฉบับร่าง"
        }
        actions={
          <Link href="/admin/notifications">
            <Button size="sm" variant="secondary">
              ← กลับ
            </Button>
          </Link>
        }
      />

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-4">
          {/* ---- 1 · Type ---- */}
          <AdminPanel
            title="ประเภทประกาศ"
            description="ตัวเลือกปิด - ประเภทเป็นตัวกำหนดไอคอนและสีที่ผู้รับเห็น ไม่ใช่แค่ป้ายจัดหมวด"
          >
            <div className="grid gap-1.5 px-4 py-3 sm:grid-cols-2 lg:grid-cols-3">
              {ANNOUNCEMENT_KIND_OPTIONS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  aria-pressed={kind === item.key}
                  onClick={() => setKind(item.key)}
                  className={cn(
                    "flex items-start gap-2.5 rounded-md border px-2.5 py-2 text-left",
                    kind === item.key
                      ? "border-accent bg-accent-subtle"
                      : "border-edge bg-surface hover:border-edge-strong",
                  )}
                >
                  {/* The real glyph and colour, not a stand-in: what the
                      picker shows is what lands in the inbox. */}
                  <span
                    aria-hidden
                    className={cn(
                      "flex size-8 shrink-0 items-center justify-center rounded-full",
                      item.tone,
                    )}
                  >
                    <Icon tint name={`ui/${item.icon}`} className="size-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-fg">
                      {item.label}
                    </span>
                    <span className="block text-xs text-fg-muted">
                      {item.description}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </AdminPanel>

          {/* ---- 2 · Content ---- */}
          {daysSinceLastSend !== null && daysSinceLastSend < 7 ? (
            <p
              role="status"
              className="rounded-md border border-warning/40 bg-warning-subtle px-3 py-2 text-sm text-fg"
            >
              ส่งประกาศล่าสุดไปเมื่อ{" "}
              {daysSinceLastSend === 0
                ? "วันนี้"
                : `${daysSinceLastSend} วันก่อน`}{" "}
              - ส่งถี่เกินสัปดาห์ละครั้งคือเหตุผลอันดับหนึ่งที่คนปิดการแจ้งเตือนทั้งหมด
            </p>
          ) : null}

          <AdminPanel title="เนื้อหา" required>
            <div className="space-y-3 px-4 py-3">
              {/* The reader's card is one headline and one line of
                  text; these limits are the card's, not the column's. */}
              <Field label="หัวข้อ" required>
                {(control) => (
                  <>
                    <Input
                      {...control}
                      ref={titleRef}
                      value={title}
                      maxLength={TITLE_LIMIT}
                      placeholder="เช่น สูตรใหม่ประจำสัปดาห์"
                      onFocus={() => setLastFocus("title")}
                      onChange={(event) => setTitle(event.target.value)}
                    />
                    <CharCount value={title} limit={TITLE_LIMIT} />
                  </>
                )}
              </Field>

              <Field label="ข้อความ">
                {(control) => (
                  <>
                    <Textarea
                      {...control}
                      ref={bodyRef}
                      rows={3}
                      value={body}
                      maxLength={BODY_LIMIT}
                      placeholder="เช่น สวัสดี {{user_name}} สัปดาห์นี้เรามีสูตรใหม่มาให้ลอง"
                      onFocus={() => setLastFocus("body")}
                      onChange={(event) => setBody(event.target.value)}
                    />
                    <CharCount value={body} limit={BODY_LIMIT} />
                  </>
                )}
              </Field>

              <div>
                <p className="mb-1 text-xs font-medium text-fg-muted">
                  ตัวแปร - คลิกเพื่อแทรกในช่องที่กำลังพิมพ์
                </p>
                <div className="flex flex-wrap gap-1">
                  {VARIABLES.map((variable) => {
                    const usable =
                      variable.availability === "always" ||
                      (variable.availability === "course" &&
                        (audKind === "course_enrolled" ||
                          audKind === "course_completed"));
                    return (
                      <button
                        key={variable.name}
                        type="button"
                        title={
                          usable
                            ? `ตัวอย่าง: ${variable.sample}`
                            : "ใช้แสดงตัวอย่างเท่านั้น - ระบบจะไม่ยอมส่งจริงกับกลุ่มเป้าหมายนี้"
                        }
                        onClick={() => insertVariable(variable.name)}
                        className={cn(
                          "rounded-full border px-2 py-0.5 font-mono text-xs",
                          usable
                            ? "border-accent/40 bg-accent-subtle text-fg"
                            : "border-edge bg-surface-sunken text-fg-subtle",
                        )}
                      >
                        {"{{"}
                        {variable.name}
                        {"}}"} · {variable.label}
                      </button>
                    );
                  })}
                </div>
                {blocked.length > 0 ? (
                  <p role="alert" className="mt-1.5 text-xs text-warning">
                    ⚠ ตัวแปร {blocked.map((name) => `{{${name}}}`).join(", ")}{" "}
                    ใช้กับกลุ่มเป้าหมายนี้ไม่ได้ - ส่งจริง/ตั้งเวลาไม่ได้จนกว่าจะเอาออก
                    (บันทึกฉบับร่างได้)
                  </p>
                ) : null}
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="ข้อความปุ่ม CTA" hint="แสดงเมื่อมีลิงก์ปลายทาง">
                  {(control) => (
                    <Input
                      {...control}
                      value={ctaText}
                      maxLength={60}
                      placeholder="เช่น ดูโพสต์"
                      onChange={(event) => setCtaText(event.target.value)}
                    />
                  )}
                </Field>
                {/* Required, and chosen rather than typed: an
                    announcement with nowhere to go is a notification the
                    reader can do nothing about. */}
                <Field label="ลิงก์ปลายทาง" required>
                  {(control) => (
                    <>
                      <select
                        {...control}
                        value={
                          DESTINATIONS.some((item) => item.href === link)
                            ? link
                            : "custom"
                        }
                        onChange={(event) =>
                          setLink(
                            event.target.value === "custom"
                              ? ""
                              : event.target.value,
                          )
                        }
                        className="h-10 w-full rounded-md border border-edge bg-surface px-3 text-sm"
                      >
                        {DESTINATIONS.map((item) => (
                          <option key={item.href} value={item.href}>
                            {item.label}
                          </option>
                        ))}
                        <option value="custom">ระบุเส้นทางเอง…</option>
                      </select>
                      {!DESTINATIONS.some((item) => item.href === link) ? (
                        <Input
                          value={link}
                          maxLength={300}
                          placeholder="/recipes/choc-chip-cookies"
                          aria-label="เส้นทางปลายทาง"
                          className="mt-1.5"
                          onChange={(event) => setLink(event.target.value)}
                        />
                      ) : null}
                    </>
                  )}
                </Field>
              </div>
            </div>
          </AdminPanel>

          {/* ---- 3 · Audience (locked after send) ---- */}
          {sentLocked ? (
            <AdminPanel title="กลุ่มเป้าหมายและการส่ง">
              <p className="px-4 py-3 text-sm text-fg-muted">
                แคมเปญนี้ส่งแล้วถึง{" "}
                <span className="font-mono font-semibold tabular-nums">
                  {sentRecipients.toLocaleString("th-TH")}
                </span>{" "}
                บัญชี - กลุ่มเป้าหมายและเวลาส่งเป็นประวัติ แก้ไขไม่ได้
                หากต้องการถอนออกจากกล่องผู้รับ ใช้ “ลบและเรียกคืน”
                จากหน้ารายการ
              </p>
            </AdminPanel>
          ) : (
          <AdminPanel
            title="กลุ่มเป้าหมาย"
            description="ระบบประเมินจำนวนผู้รับด้วยเงื่อนไขเดียวกับการส่งจริง (หักผู้ที่ปิดรับประกาศแล้ว)"
            required
          >
            <div className="space-y-3 px-4 py-3">
              <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                {AUDIENCE_KINDS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    aria-pressed={audKind === item.key}
                    onClick={() => setAudKind(item.key)}
                    className={cn(
                      "rounded-md border px-2.5 py-2 text-left",
                      audKind === item.key
                        ? "border-accent bg-accent-subtle"
                        : "border-edge bg-surface hover:border-edge-strong",
                    )}
                  >
                    <span className="block text-sm font-medium text-fg">
                      {item.label}
                    </span>
                    <span className="block text-xs text-fg-muted">
                      {item.description}
                    </span>
                  </button>
                ))}
              </div>

              {audKind === "active" || audKind === "new_users" ? (
                <Field label="ภายในกี่วัน" hint="1-365 วัน">
                  {(control) => (
                    <Input
                      {...control}
                      inputMode="numeric"
                      value={days}
                      className="max-w-28"
                      onChange={(event) => setDays(event.target.value)}
                    />
                  )}
                </Field>
              ) : null}

              {courseScoped ? (
                <div className="space-y-2">
                  {courseSlug ? (
                    <p className="text-sm">
                      คอร์สที่เลือก:{" "}
                      <span className="rounded bg-accent-subtle px-2 py-0.5 font-medium">
                        {courseTitle || courseSlug}
                      </span>{" "}
                      <button
                        type="button"
                        className="text-xs text-fg-muted underline"
                        onClick={() => {
                          setCourseSlug("");
                          setCourseTitle("");
                        }}
                      >
                        เปลี่ยน
                      </button>
                    </p>
                  ) : (
                    <>
                      <SearchInput
                        value={courseSearch}
                        onChange={setCourseSearch}
                        placeholder="ค้นหาชื่อคอร์ส…"
                        label="ค้นหาคอร์ส"
                      />
                      <div className="max-h-40 space-y-1 overflow-y-auto">
                        {courses.loading ? (
                          <Skeleton className="h-8 w-full rounded" />
                        ) : (
                          courses.rows.slice(0, 8).map((course) => (
                            <button
                              key={course.slug}
                              type="button"
                              onClick={() => {
                                setCourseSlug(course.slug);
                                setCourseTitle(course.title);
                              }}
                              className="block w-full rounded border border-edge bg-surface px-2.5 py-1.5 text-left text-sm hover:border-edge-strong"
                            >
                              {course.title}{" "}
                              <span className="font-mono text-xs text-fg-subtle">
                                {course.slug}
                              </span>
                            </button>
                          ))
                        )}
                      </div>
                    </>
                  )}
                </div>
              ) : null}

              {audKind === "skill_level" ? (
                <Field label="ระดับฝีมือ">
                  {(control) => (
                    <select
                      {...control}
                      value={level}
                      onChange={(event) => setLevel(event.target.value)}
                      className="h-10 w-full max-w-56 rounded-md border border-edge bg-surface px-3 text-sm"
                    >
                      {SKILL_LEVELS.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  )}
                </Field>
              ) : null}

              {audKind === "specific_users" ? (
                <Field
                  label="ชื่อผู้ใช้"
                  hint="คั่นด้วยเว้นวรรคหรือลูกน้ำ สูงสุด 100 บัญชี"
                >
                  {(control) => (
                    <Textarea
                      {...control}
                      rows={2}
                      value={usernamesText}
                      placeholder="เช่น mildbakes, p16fan0"
                      onChange={(event) => setUsernamesText(event.target.value)}
                    />
                  )}
                </Field>
              ) : null}

              <div
                role="status"
                className="rounded-md border border-edge bg-surface px-3 py-2 text-sm"
              >
                {!doc ? (
                  <span className="text-fg-muted">
                    กรอกเงื่อนไขให้ครบเพื่อประเมินจำนวนผู้รับ
                  </span>
                ) : estimate.loading || estimate.forDoc !== docJson ? (
                  <span className="text-fg-muted">กำลังประเมินจำนวนผู้รับ…</span>
                ) : estimate.error ? (
                  <span className="text-danger">{estimate.error}</span>
                ) : (
                  <>
                    ผู้รับโดยประมาณ:{" "}
                    <span className="font-mono font-semibold tabular-nums">
                      {(estimate.count ?? 0).toLocaleString("th-TH")}
                    </span>{" "}
                    บัญชี
                  </>
                )}
              </div>
            </div>
          </AdminPanel>
          )}

          {/* ---- 4 · Delivery (absent after send) ---- */}
          {sentLocked ? null : (
          <AdminPanel title="การส่ง" required>
            <div className="space-y-3 px-4 py-3">
              <div
                role="radiogroup"
                aria-label="รูปแบบการส่ง"
                className="grid gap-1.5 sm:grid-cols-3"
              >
                {(
                  [
                    { key: "now", label: "ส่งทันที", hint: "ยืนยันก่อนส่งเสมอ" },
                    {
                      key: "schedule",
                      label: "ตั้งเวลา",
                      hint: "ส่งอัตโนมัติเมื่อถึงเวลา",
                    },
                    {
                      key: "draft",
                      label: "บันทึกฉบับร่าง",
                      hint: "เก็บไว้ส่งภายหลัง",
                    },
                  ] as const
                ).map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    role="radio"
                    aria-checked={mode === item.key}
                    onClick={() => setMode(item.key)}
                    className={cn(
                      "rounded-md border px-2.5 py-2 text-left",
                      mode === item.key
                        ? "border-accent bg-accent-subtle"
                        : "border-edge bg-surface hover:border-edge-strong",
                    )}
                  >
                    <span className="block text-sm font-medium text-fg">
                      {item.label}
                    </span>
                    <span className="block text-xs text-fg-muted">
                      {item.hint}
                    </span>
                  </button>
                ))}
              </div>

              {mode === "schedule" ? (
                <div className="space-y-1.5">
                  <Field label="ส่งเมื่อ" hint="เวลาประเทศไทย (ตามเครื่องของคุณ)">
                    {(control) => (
                      <Input
                        {...control}
                        type="datetime-local"
                        value={scheduledAt}
                        className="max-w-64"
                        onChange={(event) => setScheduledAt(event.target.value)}
                      />
                    )}
                  </Field>
                  <p className="text-xs text-fg-muted">
                    ระบบส่งตามเวลาโดย dispatcher (Celery beat หรือคำสั่ง{" "}
                    <code className="font-mono">dispatch_campaigns</code>) -
                    ถ้า dispatcher ไม่ทำงาน รายการที่ถึงกำหนดจะขึ้นป้าย
                    “ถึงกำหนดแล้ว” ให้กดส่งเองได้จากหน้ารายการ
                  </p>
                </div>
              ) : null}
            </div>
          </AdminPanel>
          )}

          {fieldError ? (
            <p role="alert" className="text-sm text-danger">
              {fieldError}
            </p>
          ) : null}

          <div className="flex flex-wrap justify-end gap-2">
            <Link href="/admin/notifications">
              <Button variant="secondary" disabled={busy}>
                ยกเลิก
              </Button>
            </Link>
            {sentLocked ? (
              <Button loading={busy} onClick={amendSent}>
                บันทึกและอัปเดตผู้รับ
              </Button>
            ) : (
              <>
                {mode !== "draft" ? (
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={saveDraft}
                  >
                    บันทึกฉบับร่าง
                  </Button>
                ) : null}
                {mode === "now" ? (
                  <Button loading={busy} onClick={sendNow}>
                    ส่งตอนนี้
                  </Button>
                ) : mode === "schedule" ? (
                  <Button loading={busy} onClick={schedule}>
                    ตั้งเวลาส่ง
                  </Button>
                ) : (
                  <Button loading={busy} onClick={saveDraft}>
                    บันทึกฉบับร่าง
                  </Button>
                )}
              </>
            )}
          </div>
        </div>

        {/* ---- Live preview ---- */}
        <aside className="space-y-2 lg:sticky lg:top-4">
          <AdminPanel
            title="ตัวอย่าง"
            description="อัปเดตทันทีตามเนื้อหา - ตัวแปรแสดงด้วยค่าตัวอย่าง"
            actions={
              <button
                type="button"
                aria-pressed={compactPreview}
                onClick={() => setCompactPreview((state) => !state)}
                className="rounded border border-edge px-2 py-0.5 text-xs text-fg-muted hover:text-fg"
              >
                {compactPreview ? "จอกว้าง" : "จอมือถือ"}
              </button>
            }
          >
            <div className="flex justify-center bg-surface-sunken/50 px-4 py-5">
              <NotificationPreviewCard
                title={title}
                body={body}
                ctaText={ctaText}
                link={link}
                kind={kind}
                compact={compactPreview}
              />
            </div>
          </AdminPanel>
          <p className="text-xs text-fg-muted">
            ตัวแปรที่กลุ่มเป้าหมายไม่รองรับจะถูกปฏิเสธตอนส่งจริง -
            ตัวอย่างนี้ใช้ค่าจำลองเพื่อให้เห็นหน้าตาเท่านั้น
          </p>
        </aside>
      </div>

      {confirm.dialog}
    </>
  );
}

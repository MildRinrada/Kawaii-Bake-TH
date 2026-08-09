"use client";

/**
 * Settings: real forms against the owning endpoints — profile PATCH,
 * preferences PATCH, notification toggles PATCH (owned by the
 * notifications domain). Reads come from the `/me/settings/` composition.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { MySettings } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { useAuth } from "@/lib/auth/auth-context";
import { useFormSubmit } from "@/lib/forms/use-form";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ErrorState } from "@/components/ui/error-state";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

const NOTIFICATION_LABELS: Record<string, string> = {
  review_received: "มีคนรีวิวผลงานของฉัน",
  course_enrollment: "มีผู้เรียนใหม่ในคอร์สของฉัน",
  achievement_earned: "ได้รับเหรียญความสำเร็จ",
  qa_answer_received: "มีคนตอบคำถามของฉัน",
  qa_answer_accepted: "คำตอบของฉันถูกเลือก",
};

function SettingsContent() {
  const { refresh } = useAuth();
  const { toast } = useToast();
  const settings = useApiQuery(
    (signal) => api.get<MySettings>("/me/settings/", { signal }),
    [],
  );

  const profileForm = useFormSubmit();
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [location, setLocation] = useState("");
  const [experience, setExperience] = useState("beginner");
  const [locale, setLocale] = useState("th");

  // Seed the form once when data arrives — derived during render (the
  // React-documented alternative to a setState effect).
  const [seeded, setSeeded] = useState(false);
  if (settings.data && !seeded) {
    setSeeded(true);
    setDisplayName(settings.data.profile.display_name);
    setBio(settings.data.profile.bio);
    setLocation(settings.data.profile.location);
    setExperience(settings.data.profile.experience_level);
    setLocale(settings.data.preferences.locale);
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    const ok = await profileForm.submit(async () => {
      await api.patch("/users/profile/update/", {
        body: {
          display_name: displayName,
          bio,
          location,
          experience_level: experience,
        },
      });
      await api.patch("/users/preferences/", { body: { locale } });
    });
    if (ok) {
      toast("บันทึกโปรไฟล์แล้ว 🎀", "success");
      settings.refetch();
      void refresh();
    }
  }

  async function toggleNotification(event_type: string, enabled: boolean) {
    try {
      await api.patch("/me/notifications/preferences/", {
        body: { [event_type]: enabled },
      });
      settings.refetch();
    } catch {
      toast("บันทึกไม่สำเร็จ", "danger");
    }
  }

  if (settings.loading) {
    return (
      <div className="space-y-4" aria-busy="true">
        <Skeleton className="h-64 w-full rounded-surface" />
        <Skeleton className="h-40 w-full rounded-surface" />
      </div>
    );
  }
  if (settings.error || !settings.data) {
    return <ErrorState error={settings.error} onRetry={settings.refetch} />;
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="self-start">
        <CardHeader title="โปรไฟล์" />
        <CardBody>
          <form onSubmit={saveProfile} className="space-y-4" noValidate>
            {profileForm.formError ? (
              <p role="alert" className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger">
                {profileForm.formError}
              </p>
            ) : null}
            <Field label="ชื่อที่แสดง" errors={profileForm.fieldErrors.display_name}>
              {(control) => (
                <Input
                  {...control}
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                />
              )}
            </Field>
            <Field label="แนะนำตัว" errors={profileForm.fieldErrors.bio}>
              {(control) => (
                <Textarea
                  {...control}
                  value={bio}
                  onChange={(event) => setBio(event.target.value)}
                  placeholder="เล่าเรื่องการอบขนมของคุณ…"
                />
              )}
            </Field>
            <Field label="ที่อยู่ (เมือง)" errors={profileForm.fieldErrors.location}>
              {(control) => (
                <Input
                  {...control}
                  value={location}
                  onChange={(event) => setLocation(event.target.value)}
                />
              )}
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="ระดับประสบการณ์" errors={profileForm.fieldErrors.experience_level}>
                {(control) => (
                  <Select
                    {...control}
                    value={experience}
                    onChange={(event) => setExperience(event.target.value)}
                  >
                    <option value="beginner">มือใหม่หัดอบ</option>
                    <option value="intermediate">พออบเป็น</option>
                    <option value="advanced">สายอบตัวจริง</option>
                    <option value="professional">มืออาชีพ</option>
                  </Select>
                )}
              </Field>
              <Field label="ภาษา" errors={profileForm.fieldErrors.locale}>
                {(control) => (
                  <Select
                    {...control}
                    value={locale}
                    onChange={(event) => setLocale(event.target.value)}
                  >
                    <option value="th">ไทย</option>
                    <option value="en">English</option>
                  </Select>
                )}
              </Field>
            </div>
            <Button type="submit" loading={profileForm.submitting}>
              บันทึกโปรไฟล์
            </Button>
          </form>
        </CardBody>
      </Card>

      <Card className="self-start">
        <CardHeader title="การแจ้งเตือน" />
        <CardBody>
          <p className="mb-4 text-sm text-fg-muted">
            เลือกเหตุการณ์ที่อยากให้แจ้งเตือนในแอป
          </p>
          <ul className="space-y-2.5">
            {Object.entries(settings.data.notifications).map(([event, enabled]) => (
              <li key={event} className="flex items-center justify-between gap-3">
                <span className="text-sm text-fg">
                  {NOTIFICATION_LABELS[event] ?? event}
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={enabled}
                  aria-label={NOTIFICATION_LABELS[event] ?? event}
                  onClick={() => void toggleNotification(event, !enabled)}
                  className={cn(
                    "relative h-6 w-11 shrink-0 rounded-full transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                    enabled ? "bg-accent" : "bg-edge-strong/60",
                  )}
                >
                  <span
                    aria-hidden
                    className={cn(
                      "absolute top-0.5 size-5 rounded-full bg-surface shadow-raised transition-[left]",
                      enabled ? "left-5.5" : "left-0.5",
                    )}
                  />
                </button>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <PageContainer>
      <RequireAuth>
        <PageHeader title="ตั้งค่า" description="โปรไฟล์ ภาษา และการแจ้งเตือนของคุณ" />
        <SettingsContent />
      </RequireAuth>
    </PageContainer>
  );
}

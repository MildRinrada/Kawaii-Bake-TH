"use client";

/**
 * Settings  "ฉันต้องการให้ระบบทำงานอย่างไร".
 *
 * The boundary this page defends: **nothing here edits who you are.**
 * Display name, avatar, bio, birthday, location and favourite categories
 * are identity, and identity is edited on `/profile`. What lives here is
 * behaviour  how content is pitched, what reaches your inbox, who can
 * see you, and the controls over the account itself. A profile card sits
 * at the top as a signpost to the other surface; it is a link, never a
 * form.
 *
 * Reads come from the `/me/settings/` composition (profile block used
 * for the signpost only). Writes go to whichever domain owns the field 
 * `/users/preferences/` for preferences, the notifications app's own
 * endpoint for per-event toggles, `/auth/` and `/users/account/` for
 * security. This page composes; it never re-implements.
 *
 * Desktop puts the section list beside the panel. Mobile shows the list
 * first and swaps to a single panel with a back link, because a sidebar
 * squeezed onto a phone is a sidebar nobody can read.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import type { MySettings } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { RequireAuth } from "@/lib/auth/require-auth";
import { ErrorState } from "@/components/ui/error-state";
import { Icon, type UiIconName } from "@/components/ui/icon";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";
import {
  AccountPanel,
  AppearancePanel,
  LearningPanel,
  NotificationsPanel,
  PrivacyPanel,
  ProfileShortcut,
} from "./sections";

type SectionId =
  | "learning"
  | "notifications"
  | "privacy"
  | "appearance"
  | "account";

const SECTIONS: Array<{
  id: SectionId;
  label: string;
  hint: string;
  icon: UiIconName;
}> = [
  {
    id: "learning",
    label: "การเรียนและการทำขนม",
    hint: "ระดับคำแนะนำ ข้อจำกัดด้านอาหาร เป้าหมายรายสัปดาห์",
    icon: "chef-hat-2",
  },
  {
    id: "notifications",
    label: "การแจ้งเตือน",
    hint: "อีเมลและการแจ้งเตือนในแอป",
    icon: "bell",
  },
  {
    id: "privacy",
    label: "ความเป็นส่วนตัว",
    hint: "ใครเห็นโปรไฟล์และข้อมูลของคุณได้บ้าง",
    icon: "lock",
  },
  {
    id: "appearance",
    label: "การแสดงผล",
    hint: "ธีมและภาษา",
    icon: "sliders",
  },
  {
    id: "account",
    label: "บัญชีและความปลอดภัย",
    hint: "รหัสผ่านและการปิดใช้งานบัญชี",
    icon: "shield",
  },
];

function SettingsContent() {
  const [active, setActive] = useState<SectionId | null>(null);
  const settings = useApiQuery(
    (signal) => api.get<MySettings>("/me/settings/", { signal }),
    [],
  );

  if (settings.loading) {
    return (
      <div aria-busy="true" className="space-y-6">
        <Skeleton className="h-24 w-full rounded-surface" />
        <div className="gap-8 lg:grid lg:grid-cols-[16rem_1fr]">
          <Skeleton className="hidden h-80 w-full rounded-surface lg:block" />
          <Skeleton className="h-96 w-full rounded-surface" />
        </div>
      </div>
    );
  }
  if (settings.error || !settings.data) {
    return <ErrorState error={settings.error} onRetry={settings.refetch} />;
  }

  const { profile, preferences, notifications } = settings.data;
  // Desktop always has a panel open; mobile starts on the category list.
  const current = active ?? "learning";
  const section = SECTIONS.find((item) => item.id === current)!;

  function panelFor(id: SectionId) {
    switch (id) {
      case "learning":
        return <LearningPanel preferences={preferences} />;
      case "notifications":
        return (
          <NotificationsPanel
            preferences={preferences}
            notifications={notifications}
          />
        );
      case "privacy":
        return <PrivacyPanel preferences={preferences} />;
      case "appearance":
        return <AppearancePanel preferences={preferences} />;
      case "account":
        return (
          <AccountPanel
            email={profile.email}
            isEmailVerified={profile.is_email_verified}
          />
        );
    }
  }

  return (
    <>
      <ProfileShortcut
        displayName={profile.display_name}
        username={profile.username}
      />

      <div className="gap-8 lg:grid lg:grid-cols-[16rem_1fr] lg:items-start">
        {/* Navigation. On mobile this is the whole screen until a
            category is chosen; on desktop it is always beside the panel. */}
        <nav
          aria-label="หมวดการตั้งค่า"
          className={cn("lg:block", active ? "hidden" : "block")}
        >
          <ul className="space-y-1.5 lg:space-y-1">
            {SECTIONS.map((item) => {
              const selected = item.id === current;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setActive(item.id)}
                    aria-current={selected ? "page" : undefined}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-surface px-4 py-3.5 text-left transition-colors",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                      // The desktop sidebar marks the open panel; on
                      // mobile nothing is "current" while the list shows.
                      selected
                        ? "bg-surface shadow-raised lg:bg-accent-subtle"
                        : "hover:bg-surface",
                    )}
                  >
                    <Icon
                      name={`ui/${item.icon}`}
                      className={cn(
                        "size-5 shrink-0",
                        selected && "lg:text-accent",
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span
                        className={cn(
                          "block text-sm font-medium",
                          selected ? "text-fg lg:text-accent" : "text-fg",
                        )}
                      >
                        {item.label}
                      </span>
                      <span className="mt-0.5 block text-xs leading-relaxed text-fg-muted lg:hidden">
                        {item.hint}
                      </span>
                    </span>
                    <Icon
                      name="ui/chevron-right"
                      className="size-4 shrink-0 text-fg-subtle lg:hidden"
                    />
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Panel. Hidden on mobile until a category is chosen. */}
        <div className={cn("lg:block", active ? "block" : "hidden")}>
          <button
            type="button"
            onClick={() => setActive(null)}
            className="mb-4 flex items-center gap-1.5 rounded-control text-sm text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-focus lg:hidden"
          >
            <Icon name="ui/arrow-left" className="size-4" />
            หมวดการตั้งค่าทั้งหมด
          </button>

          <h2 className="font-display mb-1 text-lg font-medium text-fg">
            {section.label}
          </h2>
          <p className="mb-6 text-sm text-fg-muted">{section.hint}</p>

          {panelFor(current)}
        </div>
      </div>
    </>
  );
}

export default function SettingsPage() {
  return (
    <PageContainer>
      <PageHeader
        title="ตั้งค่า"
        description="ปรับ KawaiiBake ให้เหมาะกับวิธีการเรียนและการทำขนมของคุณ"
      />
      <RequireAuth>
        <SettingsContent />
      </RequireAuth>
    </PageContainer>
  );
}

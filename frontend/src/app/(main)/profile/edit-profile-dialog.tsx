"use client";

/**
 * Edit Profile — a dedicated edit state over the profile's own endpoint,
 * not a second settings page.
 *
 * Every field here exists on `ProfileUpdateSerializer`; username is
 * absent because the account system does not allow changing it, so the
 * form does not pretend otherwise. The avatar goes in its own multipart
 * PATCH: mixing a file with a repeated-key list field in one multipart
 * body is fragile, and two small writes to the same endpoint are not.
 */

import { useRef, useState } from "react";

import { api } from "@/lib/api/client";
import type { Category, OwnProfile } from "@/lib/api/models";
import { useFormSubmit } from "@/lib/forms/use-form";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export const EXPERIENCE_LABELS: Record<string, string> = {
  beginner: "มือใหม่หัดอบ",
  intermediate: "พออบเป็น",
  advanced: "สายอบตัวจริง",
  professional: "มืออาชีพ",
};

const MAX_CATEGORIES = 10;

export function EditProfileDialog({
  open,
  profile,
  categories,
  onClose,
  onSaved,
}: {
  open: boolean;
  profile: OwnProfile;
  categories: Category[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const form = useFormSubmit();
  const fileInput = useRef<HTMLInputElement>(null);

  const [displayName, setDisplayName] = useState(profile.display_name);
  const [bio, setBio] = useState(profile.bio);
  const [location, setLocation] = useState(profile.location);
  const [experience, setExperience] = useState(profile.experience_level);
  const [picked, setPicked] = useState<string[]>([
    ...profile.favorite_categories,
  ]);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);

  function toggleCategory(slug: string) {
    setPicked((current) =>
      current.includes(slug)
        ? current.filter((item) => item !== slug)
        : current.length >= MAX_CATEGORIES
          ? current
          : [...current, slug],
    );
  }

  function chooseAvatar(file: File | undefined) {
    if (!file) return;
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(file));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const ok = await form.submit(async () => {
      await api.patch("/users/profile/update/", {
        body: {
          display_name: displayName,
          bio,
          location,
          experience_level: experience,
          favorite_categories: picked,
        },
      });
      if (avatarFile) {
        const payload = new FormData();
        payload.append("avatar", avatarFile);
        await api.patch("/users/profile/update/", { formData: payload });
      }
    });
    if (ok) onSaved();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="แก้ไขโปรไฟล์"
      className="max-w-lg"
    >
      <form onSubmit={save} className="space-y-4" noValidate>
        {form.formError ? (
          <p
            role="alert"
            className="rounded-control bg-danger-subtle px-3 py-2 text-sm text-danger"
          >
            {form.formError}
          </p>
        ) : null}

        <div className="flex items-center gap-4">
          <Avatar
            src={avatarPreview ?? profile.avatar_url}
            name={profile.display_name || profile.username}
            size="lg"
          />
          <div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => fileInput.current?.click()}
            >
              เปลี่ยนรูปโปรไฟล์
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              className="sr-only"
              aria-label="เลือกรูปโปรไฟล์"
              onChange={(event) => chooseAvatar(event.target.files?.[0])}
            />
            {avatarFile ? (
              <p className="mt-1 text-xs text-fg-muted">
                เลือกไว้: {avatarFile.name}
              </p>
            ) : null}
            {form.fieldErrors.avatar?.length ? (
              <p className="mt-1 text-xs text-danger">
                {form.fieldErrors.avatar[0]}
              </p>
            ) : null}
          </div>
        </div>

        <Field label="ชื่อที่แสดง" errors={form.fieldErrors.display_name}>
          {(control) => (
            <Input
              {...control}
              value={displayName}
              maxLength={60}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          )}
        </Field>

        <Field label="แนะนำตัว" errors={form.fieldErrors.bio}>
          {(control) => (
            <Textarea
              {...control}
              rows={3}
              value={bio}
              maxLength={500}
              placeholder="เล่าหน่อยว่าชอบอบอะไร"
              onChange={(event) => setBio(event.target.value)}
            />
          )}
        </Field>

        <Field label="ที่อยู่ / เมือง" errors={form.fieldErrors.location}>
          {(control) => (
            <Input
              {...control}
              value={location}
              maxLength={120}
              onChange={(event) => setLocation(event.target.value)}
            />
          )}
        </Field>

        <Field label="ระดับฝีมือ" errors={form.fieldErrors.experience_level}>
          {(control) => (
            <Select
              {...control}
              value={experience}
              onChange={(event) => setExperience(event.target.value)}
            >
              {Object.entries(EXPERIENCE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <fieldset>
          <legend className="text-sm font-medium text-fg">
            หมวดที่สนใจ{" "}
            <span className="font-normal text-fg-subtle">
              (เลือกได้ไม่เกิน {MAX_CATEGORIES})
            </span>
          </legend>
          <p className="mt-0.5 text-xs text-fg-muted">
            ใช้จัดอันดับสิ่งที่แนะนำให้คุณในหน้าแนะนำสำหรับคุณ
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {categories.map((category) => {
              const active = picked.includes(category.slug);
              return (
                <button
                  key={category.slug}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleCategory(category.slug)}
                  className={`rounded-full border px-3 py-1 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${
                    active
                      ? "border-accent bg-accent-subtle text-fg"
                      : "border-edge bg-surface text-fg-muted hover:border-edge-strong"
                  }`}
                >
                  {active ? "✓ " : ""}
                  {category.name}
                </button>
              );
            })}
          </div>
          {form.fieldErrors.favorite_categories?.length ? (
            <p className="mt-1 text-xs text-danger">
              {form.fieldErrors.favorite_categories[0]}
            </p>
          ) : null}
        </fieldset>

        <div className="flex justify-end gap-2 border-t border-edge pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            ยกเลิก
          </Button>
          <Button type="submit" loading={form.submitting}>
            บันทึกโปรไฟล์
          </Button>
        </div>
      </form>
    </Modal>
  );
}

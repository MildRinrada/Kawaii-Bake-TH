"use client";

/**
 * The template editor, shared by create and edit.
 *
 * Templates are **admin-side configuration** - reusable starting points
 * for the composer. They never reach a recipient themselves and have
 * nothing to do with a user's notification preferences.
 */

import { useId, useState, type FormEvent } from "react";

import { api } from "@/lib/api/client";
import type { NotificationTemplateItem } from "@/lib/api/models";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DetailPanel } from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

import { ANNOUNCEMENT_KIND_OPTIONS, DEFAULT_KIND, isKnownKind } from "./kinds";
import { NotificationPreviewCard } from "./preview-card";

export function TemplateForm({
  open,
  initial,
  onClose,
  onSaved,
}: {
  open: boolean;
  /** `null` = create mode. */
  initial: NotificationTemplateItem | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const formId = useId();
  const editing = initial !== null;

  const [name, setName] = useState(initial?.name ?? "");
  const [kind, setKind] = useState(
    initial?.kind && isKnownKind(initial.kind) ? initial.kind : DEFAULT_KIND,
  );
  const [title, setTitle] = useState(initial?.title ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [ctaText, setCtaText] = useState(initial?.cta_text ?? "");
  const [link, setLink] = useState(initial?.link ?? "");
  const [busy, setBusy] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !title.trim()) {
      setNameError("กรุณากรอกชื่อเทมเพลตและหัวข้อการแจ้งเตือน");
      return;
    }
    setNameError(null);
    setBusy(true);
    const payload = {
      name: name.trim(),
      kind,
      title: title.trim(),
      body: body.trim(),
      cta_text: ctaText.trim(),
      link: link.trim(),
    };
    try {
      if (editing) {
        await api.patch(`/admin/notifications/templates/${initial.id}/`, {
          body: payload,
        });
        toast(`บันทึกเทมเพลต “${payload.name}” แล้ว`, "success");
      } else {
        await api.post("/admin/notifications/templates/", { body: payload });
        toast(`สร้างเทมเพลต “${payload.name}” แล้ว`, "success");
      }
      onSaved();
      onClose();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <DetailPanel
      open={open}
      title={editing ? `แก้ไขเทมเพลต: ${initial.name}` : "สร้างเทมเพลต"}
      onClose={onClose}
      footer={
        <>
          <Button size="sm" variant="secondary" disabled={busy} onClick={onClose}>
            ยกเลิก
          </Button>
          <Button size="sm" type="submit" form={formId} loading={busy}>
            {editing ? "บันทึกเทมเพลต" : "สร้างเทมเพลต"}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={save} className="space-y-4" noValidate>
        <Field
          label="ชื่อเทมเพลต"
          required
          errors={nameError ? [nameError] : undefined}
          hint="ชื่อสำหรับทีมงาน เช่น “โพสต์กำลังไวรัล”"
        >
          {(control) => (
            <Input
              {...control}
              value={name}
              maxLength={100}
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>

        <Field
          label="ประเภทประกาศ"
          hint="เป็นตัวกำหนดไอคอนและสีที่ผู้รับเห็น"
        >
          {(control) => (
            <select
              {...control}
              value={kind}
              onChange={(event) => {
                setKind(event.target.value);
              }}
              className="h-10 w-full rounded-md border border-edge bg-surface px-3 text-sm"
            >
              {ANNOUNCEMENT_KIND_OPTIONS.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </select>
          )}
        </Field>

        <Field label="หัวข้อ" required hint="ใช้ตัวแปรได้ เช่น {{user_name}}">
          {(control) => (
            <Input
              {...control}
              value={title}
              maxLength={200}
              onChange={(event) => setTitle(event.target.value)}
            />
          )}
        </Field>

        <Field label="ข้อความ">
          {(control) => (
            <Textarea
              {...control}
              rows={3}
              value={body}
              maxLength={500}
              onChange={(event) => setBody(event.target.value)}
            />
          )}
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="ข้อความปุ่ม CTA">
            {(control) => (
              <Input
                {...control}
                value={ctaText}
                maxLength={60}
                placeholder="เช่น ดูเลย"
                onChange={(event) => setCtaText(event.target.value)}
              />
            )}
          </Field>
          <Field label="ลิงก์ปลายทาง">
            {(control) => (
              <Input
                {...control}
                value={link}
                maxLength={300}
                placeholder="/recipes"
                onChange={(event) => setLink(event.target.value)}
              />
            )}
          </Field>
        </div>

        <div className="space-y-1.5">
          <p className="text-sm font-medium text-fg">ตัวอย่าง</p>
          <NotificationPreviewCard
            title={title}
            body={body}
            ctaText={ctaText}
            link={link}
            kind={kind}
          />
        </div>
      </form>
    </DetailPanel>
  );
}

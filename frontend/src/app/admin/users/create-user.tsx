"use client";

/**
 * "+ เพิ่มผู้ใช้" - staff account creation (ADR 0031).
 *
 * `POST /admin/users/create/` runs the same validation pipeline as
 * self-service registration (unique email/handle, password strength).
 * Unverified accounts get the normal verification email; the "verified"
 * switch stamps the address instead - the operator vouches for it. The
 * terms stamp stays empty: the member never consented.
 */

import { useId, useState, type FormEvent } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { translateFieldErrors } from "@/lib/forms/friendly-errors";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { DetailPanel } from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

export function CreateUserPanel({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { toast } = useToast();
  const formId = useId();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!email.trim() || !username.trim() || !password) {
      setFieldErrors({
        ...(email.trim() ? {} : { email: ["กรุณากรอกอีเมล"] }),
        ...(username.trim() ? {} : { username: ["กรุณากรอกชื่อผู้ใช้"] }),
        ...(password ? {} : { password: ["กรุณากำหนดรหัสผ่าน"] }),
      });
      return;
    }
    setBusy(true);
    setFieldErrors({});
    try {
      await api.post("/admin/users/create/", {
        body: {
          email: email.trim(),
          username: username.trim(),
          password,
          ...(firstName.trim() ? { first_name: firstName.trim() } : {}),
          ...(lastName.trim() ? { last_name: lastName.trim() } : {}),
          verified,
        },
      });
      toast(
        verified
          ? `สร้างบัญชี @${username.trim()} แล้ว (ยืนยันอีเมลให้ทันที)`
          : `สร้างบัญชี @${username.trim()} แล้ว - ส่งอีเมลยืนยันให้อัตโนมัติ`,
        "success",
      );
      onCreated();
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setFieldErrors(
          error.code === "username_taken"
            ? { username: ["ชื่อผู้ใช้นี้ถูกใช้แล้ว"] }
            : { email: ["อีเมลนี้มีบัญชีอยู่แล้ว"] },
        );
      } else if (
        error instanceof ApiError &&
        Object.keys(error.details).length
      ) {
        setFieldErrors(translateFieldErrors(error.fieldErrors()));
      } else {
        toast(describeAdminError(error), "danger");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <DetailPanel
      open={open}
      title="เพิ่มผู้ใช้"
      onClose={onClose}
      footer={
        <>
          <Button size="sm" variant="secondary" disabled={busy} onClick={onClose}>
            ยกเลิก
          </Button>
          <Button size="sm" type="submit" form={formId} loading={busy}>
            สร้างบัญชี
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={save} className="space-y-4" noValidate>
        <Field label="อีเมล" required errors={fieldErrors.email}>
          {(control) => (
            <Input
              {...control}
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          )}
        </Field>

        <Field
          label="ชื่อผู้ใช้"
          required
          errors={fieldErrors.username}
          hint="a-z 0-9 และขีดล่าง สูงสุด 30 ตัวอักษร"
        >
          {(control) => (
            <Input
              {...control}
              value={username}
              maxLength={30}
              className="font-mono"
              onChange={(event) => setUsername(event.target.value)}
            />
          )}
        </Field>

        <Field
          label="รหัสผ่านเริ่มต้น"
          required
          errors={fieldErrors.password}
          hint="ผู้ใช้เปลี่ยนเองได้ทุกเมื่อ - หรือใช้ปุ่มส่งลิงก์รีเซ็ตภายหลัง"
        >
          {(control) => (
            <Input
              {...control}
              type="text"
              value={password}
              autoComplete="off"
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
        </Field>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="ชื่อจริง" errors={fieldErrors.first_name}>
            {(control) => (
              <Input
                {...control}
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
              />
            )}
          </Field>
          <Field label="นามสกุล" errors={fieldErrors.last_name}>
            {(control) => (
              <Input
                {...control}
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
              />
            )}
          </Field>
        </div>

        <Switch
          checked={verified}
          onChange={setVerified}
          disabled={busy}
          label="ทำเครื่องหมายยืนยันอีเมลแล้ว"
          description="ปิดไว้ = ระบบส่งอีเมลยืนยันให้ผู้ใช้กดเอง / เปิด = ยืนยันแทนทันที (คุณรับรองอีเมลนี้เอง)"
        />
      </form>
    </DetailPanel>
  );
}

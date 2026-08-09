"use client";

/**
 * Certificates — read-only, and that is a product rule, not a shortcut.
 *
 * Issued credentials are immutable: the ledger stores a snapshot of the
 * recipient handle, course title and dates at issue time, and nothing in
 * the API can edit them. `certificate_service.revoke()` exists in the
 * backend but **no endpoint exposes it**, so no revoke button is offered
 * here.
 *
 * The genuinely useful admin tool that does exist is verification:
 * `GET /certificates/{token}/` is a public read that answers
 * valid / revoked for any token — exactly what an operator needs when
 * someone disputes a certificate.
 */

import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Certificate, Schemas } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { formatThaiDate } from "@/components/content/certificate-sheet";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DetailRow,
  StatusBadge,
  UnavailablePanel,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

type Verification = Schemas["CertificateVerification"];

export default function AdminCertificatesPage() {
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(false);
  const [verdict, setVerdict] = useState<Verification | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const mine = useApiQuery(
    (signal) => api.get<Paginated<Certificate>>("/me/certificates/", { signal }),
    [],
  );

  async function verify(event: React.FormEvent) {
    event.preventDefault();
    const value = token.trim();
    if (!value) return;
    setChecking(true);
    setVerdict(null);
    setVerifyError(null);
    try {
      setVerdict(await api.get<Verification>(`/certificates/${value}/`));
    } catch (error) {
      setVerifyError(
        error instanceof ApiError && error.status === 404
          ? "ไม่พบใบประกาศที่ตรงกับรหัสตรวจสอบนี้"
          : describeAdminError(error),
      );
    } finally {
      setChecking(false);
    }
  }

  return (
    <>
      <AdminPageHeader
        title="ใบประกาศนียบัตร"
        description="ใบประกาศเป็นข้อมูลที่แก้ไขไม่ได้ (append-only) — หน้านี้จึงอ่านอย่างเดียวโดยตั้งใจ"
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <AdminPanel
          title="ตรวจสอบใบประกาศจากรหัส"
          description="GET /certificates/{token}/ — endpoint สาธารณะที่ตอบว่าใบนี้ใช้ได้หรือถูกเพิกถอน"
        >
          <div className="px-4 py-4">
            <form onSubmit={verify} className="flex items-end gap-2" noValidate>
              <Field label="รหัสตรวจสอบ (UUID)" className="flex-1">
                {(control) => (
                  <Input
                    {...control}
                    value={token}
                    placeholder="วางรหัสจากลิงก์ /verify/…"
                    onChange={(event) => setToken(event.target.value)}
                  />
                )}
              </Field>
              <Button type="submit" loading={checking}>
                ตรวจสอบ
              </Button>
            </form>

            {verifyError ? (
              <p role="alert" className="mt-3 text-sm text-danger">
                {verifyError}
              </p>
            ) : null}

            {verdict ? (
              <div className="mt-4">
                <StatusBadge status={verdict.status} />
                <dl className="mt-2">
                  <DetailRow label="เลขที่">
                    <span className="font-mono text-xs">
                      {verdict.certificate_number}
                    </span>
                  </DetailRow>
                  <DetailRow label="ผู้รับ">{verdict.student_name}</DetailRow>
                  <DetailRow label="คอร์ส">{verdict.course_title}</DetailRow>
                  <DetailRow label="ออกให้เมื่อ">
                    {formatThaiDate(verdict.issued_at)}
                  </DetailRow>
                </dl>
              </div>
            ) : null}
          </div>
        </AdminPanel>

        <AdminPanel
          title="ใบประกาศของบัญชีที่กำลังใช้งาน"
          description="GET /me/certificates/ — เป็นข้อมูลของคุณเอง ไม่ใช่ทะเบียนทั้งแพลตฟอร์ม"
        >
          {mine.error ? (
            <div className="p-4">
              <ErrorState error={mine.error} onRetry={mine.refetch} />
            </div>
          ) : (
            <DataTable
              caption="ใบประกาศของบัญชีนี้"
              loading={mine.loading}
              rows={mine.data?.results ?? []}
              rowKey={(row) => row.id}
              empty={<AdminEmpty title="บัญชีนี้ยังไม่มีใบประกาศ" />}
              columns={[
                {
                  key: "number",
                  header: "เลขที่",
                  render: (row) => (
                    <span className="font-mono text-xs">
                      {row.certificate_number}
                    </span>
                  ),
                },
                {
                  key: "course",
                  header: "คอร์ส",
                  render: (row) => (
                    <span className="line-clamp-1">{row.course_title}</span>
                  ),
                },
                {
                  key: "student",
                  header: "ผู้รับ",
                  render: (row) => (
                    <span className="text-fg-muted">{row.student_name}</span>
                  ),
                },
                {
                  key: "issued",
                  header: "ออกเมื่อ",
                  render: (row) => (
                    <span className="whitespace-nowrap text-xs text-fg-muted">
                      {formatThaiDate(row.issued_at)}
                    </span>
                  ),
                },
                {
                  key: "status",
                  header: "สถานะ",
                  render: (row) => <StatusBadge status={row.status} />,
                },
              ]}
            />
          )}
        </AdminPanel>
      </div>

      <div className="mt-4">
        <UnavailablePanel
          title="ทะเบียนใบประกาศและการเพิกถอน"
          what="ยังไม่มีทะเบียนใบประกาศทั้งแพลตฟอร์ม และไม่มีปุ่มเพิกถอน — บริการ revoke() มีอยู่จริงในโค้ดฝั่งเซิร์ฟเวอร์แต่ยังไม่ถูกเปิดเป็น endpoint จึงไม่ใส่ปุ่มที่กดแล้วพัง"
          missing={[
            "GET /api/v1/admin/certificates/ (ทะเบียนทั้งหมด พร้อมค้นหาตามผู้รับ/คอร์ส)",
            "POST /api/v1/certificates/{id}/revoke/ (เพิกถอน — service มีแล้ว ยังไม่มี route)",
          ]}
          workaround="เมื่อเปิด endpoint เพิกถอนแล้ว ต้องมาพร้อมเหตุผลและผู้ดำเนินการที่บันทึกได้ เพราะการเพิกถอนคือการเปลี่ยนหลักฐานการเรียนจบของคนอื่น"
        />
      </div>
    </>
  );
}

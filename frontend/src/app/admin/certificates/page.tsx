"use client";

/**
 * Certificate registry - the full platform ledger, plus revocation.
 *
 * `GET /admin/certificates/` (staff-only) lists every issued credential
 * with search across number / student name / course title / handle and a
 * valid-vs-revoked filter. Issued rows stay immutable snapshots; the one
 * write is `POST /admin/certificates/{id}/revoke/`, which requires a
 * reason (max 200 chars) because revoking changes the evidentiary answer
 * of the public verification page. Revocation is one-way: a 409
 * (`certificate_already_revoked`) means another operator got there first
 * and their reason stays on record.
 *
 * The token lookup tool (`GET /certificates/{token}/`, public) is kept
 * below the registry - it answers exactly what an operator needs when
 * someone disputes a certificate link.
 */

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { AdminCertificate, Schemas } from "@/lib/api/models";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { formatThaiDate } from "@/components/content/certificate-sheet";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  DetailPanel,
  DetailRow,
  FilterBar,
  FilterSelect,
  Pagination,
  SearchInput,
  StatusBadge,
  useConfirm,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

type Verification = Schemas["CertificateVerification"];

const STATUSES = [
  { value: "", label: "ทั้งหมด" },
  { value: "valid", label: "ใช้ได้" },
  { value: "revoked", label: "ถูกเพิกถอน" },
];

const REASON_MAX = 200;

export default function AdminCertificatesPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<AdminCertificate | null>(null);

  // Inline revoke form (revealed inside the detail panel footer).
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);

  const list = usePagedList<AdminCertificate>("/admin/certificates/", {
    search: search || undefined,
    status: status || undefined,
  });

  // Prefer the freshest copy of the selected row: after a refetch the
  // table row wins; the snapshot covers rows filtered off the page.
  const current = selected
    ? (list.rows.find((row) => row.id === selected.id) ?? selected)
    : null;

  function resetRevokeForm() {
    setRevokeOpen(false);
    setReason("");
    setReasonError(null);
  }

  function openDetail(row: AdminCertificate) {
    setSelected(row);
    resetRevokeForm();
  }

  function closeDetail() {
    setSelected(null);
    resetRevokeForm();
  }

  async function revoke(cert: AdminCertificate, value: string) {
    try {
      const updated = await api.post<AdminCertificate>(
        `/admin/certificates/${cert.id}/revoke/`,
        { body: { reason: value } },
      );
      toast(`เพิกถอนใบประกาศ ${updated.certificate_number} แล้ว`, "success");
      setSelected(updated);
      resetRevokeForm();
      list.refetch();
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.status === 409 &&
        error.code === "certificate_already_revoked"
      ) {
        // First operator wins: their reason stays on record.
        toast(
          "ใบประกาศนี้ถูกเพิกถอนไปก่อนแล้วโดยผู้ดูแลคนอื่น เหตุผลเดิมยังคงอยู่",
          "danger",
        );
        resetRevokeForm();
        list.refetch();
      } else {
        toast(describeAdminError(error), "danger");
      }
    }
  }

  function submitRevoke(event: React.FormEvent) {
    event.preventDefault();
    if (!current) return;
    const value = reason.trim();
    if (!value) {
      setReasonError("กรุณาระบุเหตุผลในการเพิกถอน");
      return;
    }
    if (value.length > REASON_MAX) {
      setReasonError(`เหตุผลต้องยาวไม่เกิน ${REASON_MAX} ตัวอักษร`);
      return;
    }
    const cert = current;
    confirm.ask({
      title: "เพิกถอนใบประกาศนี้?",
      body: `หน้าตรวจสอบสาธารณะของใบ ${cert.certificate_number} จะเปลี่ยนคำตอบจาก “ใช้ได้” เป็น “ถูกเพิกถอน” ทันที นี่คือการเปลี่ยนหลักฐานการเรียนจบของ ${cert.student_name} และย้อนกลับไม่ได้จากหน้านี้`,
      confirmLabel: "เพิกถอน",
      danger: true,
      action: () => revoke(cert, value),
    });
  }

  // --- Token verification tool (carried over, behavior unchanged) ---
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(false);
  const [verdict, setVerdict] = useState<Verification | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

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
        title="ใบประกาศ"
        description="ทะเบียนใบประกาศทั้งแพลตฟอร์ม  ค้นหา ดูรายละเอียด และเพิกถอนพร้อมเหตุผลเมื่อจำเป็น"
      />

      <AdminPanel>
        {list.error ? (
          <div className="p-4">
            <ErrorState error={list.error} onRetry={list.refetch} />
          </div>
        ) : (
          <>
            <DataTableToolbar
              actions={
                <span className="self-center text-xs text-fg-muted">
                  ทั้งหมด{" "}
                  <span className="font-mono tabular-nums">{list.count}</span>{" "}
                  รายการ
                </span>
              }
            >
              <SearchInput
                value={searchInput}
                onChange={setSearchInput}
                placeholder="ค้นหาเลขที่ / ชื่อผู้เรียน / คอร์ส…"
                label="ค้นหาใบประกาศ"
              />
              <FilterBar>
                <FilterSelect
                  label="สถานะ"
                  value={status}
                  options={STATUSES}
                  onChange={setStatus}
                />
              </FilterBar>
            </DataTableToolbar>

            <DataTable
              caption="ทะเบียนใบประกาศทั้งแพลตฟอร์ม"
              loading={list.loading}
              rows={list.rows}
              rowKey={(row) => row.id}
              onRowClick={openDetail}
              empty={
                <AdminEmpty
                  title="ไม่พบใบประกาศที่ตรงกับเงื่อนไข"
                  description="ลองล้างคำค้นหรือเปลี่ยนตัวกรองสถานะ"
                />
              }
              columns={[
                {
                  key: "number",
                  header: "เลขที่",
                  render: (row) => (
                    <span className="whitespace-nowrap font-mono text-xs">
                      {row.certificate_number}
                    </span>
                  ),
                },
                {
                  key: "recipient",
                  header: "ผู้รับ",
                  render: (row) => (
                    <div className="min-w-0">
                      <p className="line-clamp-1 font-medium">
                        {row.student_name}
                      </p>
                      <p className="text-xs text-fg-subtle">@{row.username}</p>
                    </div>
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
                  key: "issued",
                  header: "ออกให้เมื่อ",
                  render: (row) => (
                    <span className="whitespace-nowrap text-xs text-fg-muted">
                      {relativeThai(row.issued_at)}
                    </span>
                  ),
                },
                {
                  key: "status",
                  header: "สถานะ",
                  render: (row) => <StatusBadge status={row.status} />,
                },
                {
                  key: "revocation",
                  header: "การเพิกถอน",
                  render: (row) =>
                    row.status === "revoked" ? (
                      <div className="min-w-0">
                        <p className="line-clamp-1 text-xs text-fg-muted">
                          {row.revoked_reason}
                        </p>
                        {row.revoked_by ? (
                          <p className="text-xs text-fg-subtle">
                            โดย @{row.revoked_by}
                          </p>
                        ) : null}
                      </div>
                    ) : (
                      <span className="text-fg-subtle">-</span>
                    ),
                },
              ]}
            />

            <Pagination
              page={list.page}
              pageSize={list.pageSize}
              count={list.count}
              onPage={list.setPage}
            />
          </>
        )}
      </AdminPanel>

      <AdminPanel
        className="mt-4"
        title="ตรวจสอบใบประกาศจากรหัส"
        description="GET /certificates/{token}/  endpoint สาธารณะที่ตอบว่าใบนี้ใช้ได้หรือถูกเพิกถอน"
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

      <DetailPanel
        open={current !== null}
        title={
          current
            ? `ใบประกาศ ${current.certificate_number}`
            : "รายละเอียดใบประกาศ"
        }
        onClose={closeDetail}
        footer={
          current && current.status === "valid" ? (
            revokeOpen ? (
              <form onSubmit={submitRevoke} className="w-full space-y-2" noValidate>
                <Field
                  label="เหตุผลในการเพิกถอน"
                  required
                  errors={reasonError ? [reasonError] : undefined}
                  hint={`จะถูกบันทึกถาวรพร้อมชื่อผู้ดำเนินการ (ไม่เกิน ${REASON_MAX} ตัวอักษร)`}
                >
                  {(control) => (
                    <Input
                      {...control}
                      value={reason}
                      maxLength={REASON_MAX}
                      placeholder="เช่น ออกใบให้ผิดบัญชี / ตรวจพบการทุจริตในคอร์ส"
                      onChange={(event) => {
                        setReason(event.target.value);
                        setReasonError(null);
                      }}
                    />
                  )}
                </Field>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={resetRevokeForm}
                  >
                    ยกเลิก
                  </Button>
                  <Button type="submit" size="sm" variant="danger">
                    ยืนยันการเพิกถอน
                  </Button>
                </div>
              </form>
            ) : (
              <Button
                size="sm"
                variant="danger"
                onClick={() => setRevokeOpen(true)}
              >
                เพิกถอนใบประกาศ
              </Button>
            )
          ) : null
          // A revoked certificate offers no action: revocation is one-way.
        }
      >
        {current ? (
          <dl>
            <DetailRow label="เลขที่">
              <span className="font-mono text-xs">
                {current.certificate_number}
              </span>
            </DetailRow>
            <DetailRow label="ผู้รับ">
              {current.display_name}{" "}
              <span className="text-xs text-fg-subtle">@{current.username}</span>
            </DetailRow>
            <DetailRow label="ชื่อที่พิมพ์บนใบ">{current.student_name}</DetailRow>
            <DetailRow label="คอร์ส">{current.course_title}</DetailRow>
            <DetailRow label="เรียนจบเมื่อ">
              {formatThaiDate(current.completed_at)}
            </DetailRow>
            <DetailRow label="ออกให้เมื่อ">
              {formatThaiDate(current.issued_at)}
            </DetailRow>
            <DetailRow label="รหัสตรวจสอบ">
              <span className="font-mono text-xs">
                {current.verification_token}
              </span>{" "}
              <Link
                href={`/verify/${encodeURIComponent(current.verification_token)}`}
                target="_blank"
                rel="noreferrer"
                className="whitespace-nowrap text-xs text-accent underline underline-offset-2 hover:text-accent-hover"
              >
                เปิดหน้าตรวจสอบ
              </Link>
            </DetailRow>
            <DetailRow label="สถานะ">
              <StatusBadge status={current.status} />
            </DetailRow>
            {current.status === "revoked" ? (
              <>
                <DetailRow label="เพิกถอนเมื่อ">
                  {current.revoked_at ? formatThaiDate(current.revoked_at) : ""}
                </DetailRow>
                <DetailRow label="เพิกถอนโดย">
                  {current.revoked_by ? `@${current.revoked_by}` : ""}
                </DetailRow>
                <DetailRow label="เหตุผล">
                  <span className="text-fg-muted">{current.revoked_reason}</span>
                </DetailRow>
              </>
            ) : null}
          </dl>
        ) : null}
      </DetailPanel>

      {confirm.dialog}
    </>
  );
}

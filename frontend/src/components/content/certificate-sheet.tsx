/**
 * The certificate itself, rendered from the credential's real stored
 * fields — the same immutable snapshot the backend issued (recipient,
 * course, dates, number). Not a placeholder image: there is no
 * certificate asset in the system, so the document *is* this render,
 * and printing it (browser → Save as PDF) is the honest download path.
 */

import { cn } from "@/lib/cn";

export interface CertificateFields {
  certificate_number: string;
  course_title: string;
  student_name: string;
  issued_at: string;
  completed_at?: string;
  status: string;
}

export function formatThaiDate(value: string): string {
  return new Date(value).toLocaleDateString("th-TH", { dateStyle: "long" });
}

export function CertificateSheet({
  certificate,
  className,
}: {
  certificate: CertificateFields;
  className?: string;
}) {
  const revoked = certificate.status === "revoked";
  return (
    <article
      aria-label={`ใบประกาศนียบัตรคอร์ส ${certificate.course_title} ของ ${certificate.student_name} เลขที่ ${certificate.certificate_number}`}
      className={cn(
        "kb-certificate relative aspect-[1.414/1] w-full overflow-hidden rounded-surface bg-surface p-[5%] text-center",
        "border border-butter-ink/25 shadow-raised",
        revoked && "opacity-70 grayscale",
        className,
      )}
    >
      {/* Inner rule — the printed border of the document */}
      <div className="flex h-full w-full flex-col items-center justify-center gap-[2.5%] rounded-control border-2 border-butter-ink/30 px-[6%]">
        <p className="font-display flex items-center gap-1.5 text-[clamp(0.6rem,1.6cqw,0.9rem)] font-medium tracking-wide text-fg-muted">
          <span aria-hidden>🧁</span> KawaiiBake
        </p>
        <p className="text-[clamp(0.55rem,1.4cqw,0.8rem)] uppercase tracking-[0.25em] text-fg-subtle">
          Certificate of Completion
        </p>
        <p className="text-[clamp(0.55rem,1.5cqw,0.85rem)] text-fg-muted">
          ขอมอบใบประกาศนียบัตรฉบับนี้ให้แก่
        </p>
        <p className="font-display text-[clamp(1rem,3.4cqw,2rem)] font-medium leading-tight text-fg">
          {certificate.student_name}
        </p>
        <p className="text-[clamp(0.55rem,1.5cqw,0.85rem)] text-fg-muted">
          ผู้สำเร็จการเรียนคอร์ส
        </p>
        <p className="font-display text-[clamp(0.8rem,2.4cqw,1.35rem)] font-medium leading-snug text-accent">
          {certificate.course_title}
        </p>
        <div className="mt-[2%] flex w-full items-end justify-between gap-4 text-[clamp(0.5rem,1.2cqw,0.7rem)] text-fg-subtle">
          <p className="text-left">
            <span className="block text-fg-muted">ออกให้เมื่อ</span>
            {formatThaiDate(certificate.issued_at)}
          </p>
          <p aria-hidden className="text-2xl">
            📜
          </p>
          <p className="text-right">
            <span className="block text-fg-muted">เลขที่</span>
            <span className="font-mono">{certificate.certificate_number}</span>
          </p>
        </div>
      </div>
      {revoked ? (
        <p className="absolute inset-x-0 top-1/2 -translate-y-1/2 rotate-[-12deg] text-center text-[clamp(1rem,4cqw,2.5rem)] font-bold uppercase tracking-widest text-danger/70">
          ถูกเพิกถอน
        </p>
      ) : null}
    </article>
  );
}

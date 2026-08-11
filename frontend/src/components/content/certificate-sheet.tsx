/**
 * The certificate itself, rendered from the credential's real stored
 * fields  the same immutable snapshot the backend issued (recipient,
 * course, dates, number). Not a placeholder image: there is no
 * certificate asset in the system, so the document *is* this render,
 * and printing it (browser → Save as PDF) is the honest download path.
 *
 * The signature block is a deliberate design flourish, not a claim
 * about a specific person: it renders the platform's own name
 * ("KawaiiBake") in a script face, the way an institution  not an
 * individual instructor the backend has no record of  signs a
 * document. The seal beside it is likewise decorative, not a forgeable
 * mark; verification happens at the unguessable link, not the artwork.
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

/** One corner of the printed rule  mirrored via CSS transforms. */
function CornerFlourish({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 40 40"
      className={cn("absolute size-[6%] min-h-4 min-w-4 text-butter-ink/50", className)}
    >
      <path
        d="M2 20V6a4 4 0 0 1 4-4h14"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <circle cx="2" cy="20" r="2" fill="currentColor" />
    </svg>
  );
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
        "kb-certificate relative aspect-[1.414/1] w-full overflow-hidden rounded-surface p-[4%] text-center",
        "border border-butter-ink/25 bg-surface shadow-raised",
        revoked && "opacity-70 grayscale",
        className,
      )}
      style={{
        backgroundImage:
          "radial-gradient(circle at 12% 8%, var(--kb-berry-soft) 0%, transparent 32%)," +
          "radial-gradient(circle at 88% 92%, var(--kb-lavender-soft) 0%, transparent 32%)",
      }}
    >
      {/* Inner rule  the printed border of the document */}
      <div className="relative flex h-full w-full flex-col items-center rounded-control border-2 border-butter-ink/30 px-[6%] py-[3%]">
        <CornerFlourish className="left-[3%] top-[3%]" />
        <CornerFlourish className="right-[3%] top-[3%] -scale-x-100" />
        <CornerFlourish className="bottom-[3%] left-[3%] -scale-y-100" />
        <CornerFlourish className="bottom-[3%] right-[3%] -scale-100" />

        <div className="flex flex-1 flex-col items-center justify-center gap-[2%]">
          <p className="font-display text-[clamp(0.6rem,1.6cqw,0.9rem)] font-medium tracking-wide text-fg-muted">
            KawaiiBake
          </p>
          <p className="text-[clamp(0.5rem,1.3cqw,0.75rem)] uppercase tracking-[0.3em] text-fg-subtle">
            Certificate of Completion
          </p>
          <div
            aria-hidden
            className="my-[0.5%] h-px w-[18%] bg-gradient-to-r from-transparent via-butter-ink/50 to-transparent"
          />
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
        </div>

        {/* Footer: date  seal  signature, the three-column formal layout */}
        <div className="grid w-full grid-cols-3 items-end gap-[2%] text-[clamp(0.5rem,1.15cqw,0.7rem)] text-fg-subtle">
          <div className="text-left">
            <span className="block text-fg-muted">ออกให้เมื่อ</span>
            {formatThaiDate(certificate.issued_at)}
            <span className="mt-[4%] block text-fg-muted">เลขที่</span>
            <span className="font-mono">{certificate.certificate_number}</span>
          </div>

          <div className="flex justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element -- fixed local decorative SVG */}
            <img
              src="/icons/certificate/seal.svg"
              alt=""
              aria-hidden
              className="w-[26%] min-w-10 opacity-90"
            />
          </div>

          <div className="text-right">
            <p
              className="font-[family-name:var(--font-signature)] text-[clamp(1.1rem,3.6cqw,2rem)] leading-none text-berry-ink"
              aria-hidden
            >
              KawaiiBake
            </p>
            <div
              aria-hidden
              className="ml-auto mt-[2%] h-px w-[70%] bg-butter-ink/40"
            />
            <span className="mt-[3%] block">แพลตฟอร์มเรียนทำเบเกอรี่ภาษาไทย</span>
          </div>
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

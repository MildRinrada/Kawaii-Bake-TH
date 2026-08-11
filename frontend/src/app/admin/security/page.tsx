"use client";

/**
 * Security  suspicious-behaviour monitoring.
 *
 * Two views over the same data: **sources** (one row per address, with a
 * running score and a band) and **events** (the append-only log the
 * scores are computed from). Everything here is backed by
 * `/api/v1/admin/security/…`; the filter vocabulary comes from the API
 * rather than being hard-coded, so a signal kind added on the backend
 * shows up here without a frontend deploy.
 *
 * Three real staff capabilities: block for a bounded window, lift a
 * block, and mark a source reviewed. Marking reviewed changes no score
 * and deletes no evidence  the source returns to the queue by itself if
 * it trips a detector again.
 *
 * What this page deliberately does **not** claim: that developer tools
 * are blocked. `devtools_opened` and friends are browser-reported hints,
 * forgeable and noisy, and are scored at the bottom of the table. See
 * ADR 0025.
 */

import { useState } from "react";

import { api } from "@/lib/api/client";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { usePagedList, useDebounced } from "@/lib/admin/use-paged-list";
import { relativeThai } from "@/lib/datetime";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Icon } from "@/components/ui/icon";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import {
  AdminEmpty,
  AdminPanel,
  DataTable,
  DataTableToolbar,
  DetailPanel,
  DetailRow,
  FilterSelect,
  Pagination,
  SearchInput,
  StatCard,
  useConfirm,
  type Column,
  type FilterOption,
} from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";

/* ------------------------------------------------------------------ */
/* Shapes                                                              */
/* ------------------------------------------------------------------ */

interface SecurityEvent {
  id: number;
  kind: string;
  kind_label: string;
  severity: string;
  score_delta: number;
  ip: string;
  user_agent: string;
  path: string;
  method: string;
  status_code: number | null;
  actor_handle: string;
  request_id: string;
  detail: Record<string, string>;
  created_at: string;
}

interface ThreatProfile {
  id: number;
  ip: string;
  score: number;
  current_score: number;
  level: string;
  event_count: number;
  last_kind: string;
  last_kind_label: string;
  last_path: string;
  last_user_agent: string;
  first_seen_at: string;
  last_seen_at: string;
  blocked_until: string | null;
  is_blocked: boolean;
  review_state: string;
  reviewed_at: string | null;
  reviewed_by_handle: string;
  note: string;
}

interface ProfileDetail extends ThreatProfile {
  recent_events: SecurityEvent[];
}

interface Summary {
  profiles_total: number;
  profiles_by_level: Record<string, number>;
  profiles_blocked: number;
  profiles_open: number;
  events_total: number;
  events_24h: number;
  events_7d: number;
  events_by_kind_7d: Record<string, number>;
  top_offenders: { id: number; ip: string; score: number; level: string }[];
}

interface Vocabulary {
  kinds: FilterOption[];
  levels: FilterOption[];
  review_states: FilterOption[];
}

/* ------------------------------------------------------------------ */
/* Level presentation                                                  */
/* ------------------------------------------------------------------ */

const LEVEL_LABELS: Record<string, string> = {
  low: "ต่ำ",
  medium: "ปานกลาง",
  high: "สูง",
  critical: "วิกฤต",
};

/* Colour AND a shape cue  severity must never be conveyed by hue alone. */
const LEVEL_STYLE: Record<string, { chip: string; bars: number }> = {
  low: { chip: "bg-surface-sunken text-fg-muted", bars: 1 },
  medium: { chip: "bg-butter-soft text-butter-ink", bars: 2 },
  high: { chip: "bg-peach-soft text-peach-ink", bars: 3 },
  critical: { chip: "bg-danger-subtle text-danger", bars: 4 },
};

/**
 * Thai names for the signal kinds.
 *
 * The API stays the source of truth for *which* kinds exist  a kind
 * added on the backend still appears in the filters without a frontend
 * deploy. This map only translates the ones we have words for; anything
 * unknown falls back to the API's own (English, developer-facing) label,
 * so a new kind reads awkwardly for one release rather than vanishing.
 */
const KIND_LABELS: Record<string, string> = {
  honeypot_path: "เรียกหน้าที่ไม่มีอยู่จริง (กับดัก)",
  sensitive_file_probe: "ค้นหาไฟล์ลับ / ไฟล์สำรอง",
  path_traversal: "พยายามไต่ path ออกนอกโฟลเดอร์",
  sqli_probe: "ทดลองยิง SQL injection",
  xss_probe: "ทดลองยิง XSS",
  scanner_agent: "ใช้เครื่องมือสแกนช่องโหว่",
  automation_agent: "เรียกผ่านสคริปต์ (curl, requests…)",
  missing_user_agent: "ไม่ส่ง user agent มา",
  not_found_sweep: "กวาดหาหน้าเว็บรัว ๆ (404 จำนวนมาก)",
  auth_failure_burst: "ถูกปฏิเสธสิทธิ์ซ้ำ ๆ",
  request_flood: "ยิงคำขอถี่ผิดปกติ",
  devtools_opened: "น่าจะเปิด DevTools",
  view_source_attempt: "กดดูซอร์สโค้ด",
  context_menu_attempt: "คลิกขวา (ถูกระงับ)",
  console_tamper: "แก้ไข console / debugger",
};

function kindLabel(kind: string, fallback: string): string {
  return KIND_LABELS[kind] ?? fallback;
}

const REVIEW_LABELS: Record<string, string> = {
  open: "รอตรวจสอบ",
  acknowledged: "ตรวจแล้ว  เฝ้าดู",
  ignored: "ตรวจแล้ว  ปกติ",
};

function LevelBadge({ level }: { level: string }) {
  const style = LEVEL_STYLE[level] ?? LEVEL_STYLE.low!;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium",
        style.chip,
      )}
    >
      <span aria-hidden className="flex items-end gap-px">
        {[1, 2, 3, 4].map((step) => (
          <span
            key={step}
            className={cn(
              "w-0.5 rounded-full bg-current",
              step <= style.bars ? "opacity-100" : "opacity-25",
            )}
            style={{ height: `${3 + step * 2}px` }}
          />
        ))}
      </span>
      {LEVEL_LABELS[level] ?? level}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Summary strip                                                       */
/* ------------------------------------------------------------------ */

function SummaryStrip({ summary }: { summary: ReturnType<typeof useSummary> }) {
  const data = summary.data;
  const byLevel = data?.profiles_by_level ?? {};

  return (
    <div className="mb-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {(["critical", "high", "medium", "low"] as const).map((level) => (
        <StatCard
          key={level}
          label={`ระดับ${LEVEL_LABELS[level]}`}
          value={byLevel[level] ?? 0}
          loading={summary.loading}
        />
      ))}
      <StatCard
        label="ถูกบล็อกอยู่"
        value={data?.profiles_blocked}
        hint="บล็อกทุกครั้งมีวันหมดอายุ"
        loading={summary.loading}
      />
      <StatCard
        label="เหตุการณ์ 24 ชม."
        value={data?.events_24h}
        hint={data ? `ทั้งหมด ${data.events_total}` : undefined}
        loading={summary.loading}
      />
    </div>
  );
}

function useSummary() {
  return useApiQuery<Summary>(
    (signal) => api.get<Summary>("/admin/security/summary/", { signal }),
    [],
  );
}

/* ------------------------------------------------------------------ */
/* Sources                                                             */
/* ------------------------------------------------------------------ */

function SourcesTab({
  vocabulary,
  onChanged,
}: {
  vocabulary: Vocabulary | null;
  onChanged: () => void;
}) {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [level, setLevel] = useState("");
  const [reviewState, setReviewState] = useState("");
  const [blocked, setBlocked] = useState("");
  const [search, setSearch] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const debounced = useDebounced(search);

  const list = usePagedList<ThreatProfile>("/admin/security/profiles/", {
    level: level || undefined,
    review_state: reviewState || undefined,
    blocked: blocked || undefined,
    search: debounced || undefined,
  });

  const detail = useApiQuery<ProfileDetail | null>(
    (signal) =>
      openId === null
        ? Promise.resolve(null)
        : api.get<ProfileDetail>(`/admin/security/profiles/${openId}/`, { signal }),
    [openId],
  );

  async function act(run: () => Promise<unknown>, message: string) {
    setBusy(true);
    try {
      await run();
      toast(message, "success");
      list.refetch();
      detail.refetch();
      onChanged();
    } catch (error) {
      toast(describeAdminError(error), "danger");
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<ThreatProfile>[] = [
    {
      key: "ip",
      header: "แหล่งที่มา",
      render: (row) => (
        <span className="font-mono text-xs text-fg">{row.ip}</span>
      ),
    },
    {
      key: "level",
      header: "ระดับ",
      render: (row) => <LevelBadge level={row.level} />,
    },
    {
      key: "score",
      header: "คะแนน",
      numeric: true,
      render: (row) => (
        <span title={`คะแนนสะสม ${row.score.toFixed(1)} · ปัจจุบันหลังลดตามเวลา`}>
          {row.current_score.toFixed(1)}
        </span>
      ),
    },
    {
      key: "events",
      header: "เหตุการณ์",
      numeric: true,
      render: (row) => row.event_count,
    },
    {
      key: "last_kind",
      header: "พฤติกรรมล่าสุด",
      render: (row) => (
        <span className="text-xs text-fg-muted">
          {row.last_kind ? kindLabel(row.last_kind, row.last_kind_label) : ""}
        </span>
      ),
    },
    {
      key: "last_seen",
      header: "พบล่าสุด",
      render: (row) => (
        <span className="text-xs text-fg-muted">{relativeThai(row.last_seen_at)}</span>
      ),
    },
    {
      key: "state",
      header: "สถานะ",
      render: (row) => (
        <span className="flex flex-wrap items-center gap-1.5 text-xs">
          {row.is_blocked ? (
            <span className="inline-flex items-center gap-1 rounded bg-danger-subtle px-1.5 py-0.5 font-medium text-danger">
              <Icon name="ui/lock" className="size-3" />
              บล็อกอยู่
            </span>
          ) : null}
          <span className="text-fg-muted">
            {REVIEW_LABELS[row.review_state] ?? row.review_state}
          </span>
        </span>
      ),
    },
  ];

  const current = detail.data;

  return (
    <>
      <AdminPanel className="mt-3">
        <DataTableToolbar>
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="ค้นหา IP, เส้นทาง หรือ user agent"
          />
          <FilterSelect
            label="ระดับ"
            value={level}
            onChange={setLevel}
            options={[
              { value: "", label: "ทุกระดับ" },
              ...(vocabulary?.levels ?? []).map((option) => ({
                value: option.value,
                label: LEVEL_LABELS[option.value] ?? option.label,
              })),
            ]}
          />
          <FilterSelect
            label="การตรวจสอบ"
            value={reviewState}
            onChange={setReviewState}
            options={[
              { value: "", label: "ทั้งหมด" },
              ...(vocabulary?.review_states ?? []).map((option) => ({
                value: option.value,
                label: REVIEW_LABELS[option.value] ?? option.label,
              })),
            ]}
          />
          <FilterSelect
            label="การบล็อก"
            value={blocked}
            onChange={setBlocked}
            options={[
              { value: "", label: "ทั้งหมด" },
              { value: "true", label: "ถูกบล็อก" },
              { value: "false", label: "ไม่ถูกบล็อก" },
            ]}
          />
        </DataTableToolbar>

        {list.error ? (
          <ErrorState error={list.error} onRetry={list.refetch} />
        ) : (
          <>
            <DataTable
              caption="แหล่งที่มาที่มีพฤติกรรมน่าสงสัย"
              columns={columns}
              rows={list.rows}
              rowKey={(row) => row.id}
              loading={list.loading}
              onRowClick={(row) => setOpenId(row.id)}
              empty={
                <AdminEmpty
                  title="ยังไม่พบพฤติกรรมน่าสงสัย"
                  description="ระบบจะบันทึกเมื่อมีการสแกน เรียกไฟล์ลับ หรือใช้เครื่องมืออัตโนมัติ"
                />
              }
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

      <DetailPanel
        open={openId !== null}
        title={current ? `แหล่งที่มา ${current.ip}` : "กำลังโหลด…"}
        onClose={() => setOpenId(null)}
        footer={
          current ? (
            <div className="flex flex-wrap gap-2">
              {current.is_blocked ? (
                <Button
                  size="sm"
                  variant="secondary"
                  loading={busy}
                  onClick={() =>
                    act(
                      () =>
                        api.delete(`/admin/security/profiles/${current.id}/block/`),
                      "ปลดบล็อกแล้ว",
                    )
                  }
                >
                  ปลดบล็อก
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="danger"
                  loading={busy}
                  onClick={() =>
                    confirm.ask({
                      title: `บล็อก ${current.ip} 60 นาที`,
                      body: "การบล็อกมีวันหมดอายุเสมอ และ IP หนึ่งอาจเป็นผู้ใช้หลายคน (เช่น เน็ตมือถือหรือออฟฟิศ)",
                      confirmLabel: "บล็อก 60 นาที",
                      danger: true,
                      action: () =>
                        act(
                          () =>
                            api.post(
                              `/admin/security/profiles/${current.id}/block/`,
                              { body: { minutes: 60 } },
                            ),
                          "บล็อกแล้ว 60 นาที",
                        ),
                    })
                  }
                >
                  บล็อก 60 นาที
                </Button>
              )}
              <Button
                size="sm"
                variant="secondary"
                loading={busy}
                onClick={() =>
                  act(
                    () =>
                      api.post(`/admin/security/profiles/${current.id}/review/`, {
                        body: { state: "acknowledged" },
                      }),
                    "ทำเครื่องหมายว่าตรวจแล้ว",
                  )
                }
              >
                ตรวจแล้ว  เฝ้าดู
              </Button>
              <Button
                size="sm"
                variant="secondary"
                loading={busy}
                onClick={() =>
                  act(
                    () =>
                      api.post(`/admin/security/profiles/${current.id}/review/`, {
                        body: { state: "ignored" },
                      }),
                    "ทำเครื่องหมายว่าปกติ",
                  )
                }
              >
                ตรวจแล้ว  ปกติ
              </Button>
            </div>
          ) : null
        }
      >
        {current ? (
          <>
            <dl>
              <DetailRow label="ระดับ">
                <LevelBadge level={current.level} />
              </DetailRow>
              <DetailRow label="คะแนน">
                <span className="font-mono tabular-nums">
                  {current.current_score.toFixed(1)}
                </span>{" "}
                <span className="text-xs text-fg-muted">
                  (สะสม {current.score.toFixed(1)}  คะแนนลดลงครึ่งหนึ่งทุก 12 ชม.)
                </span>
              </DetailRow>
              <DetailRow label="พบครั้งแรก">
                {relativeThai(current.first_seen_at)}
              </DetailRow>
              <DetailRow label="พบล่าสุด">
                {relativeThai(current.last_seen_at)}
              </DetailRow>
              <DetailRow label="เส้นทางล่าสุด">
                <span className="font-mono text-xs">{current.last_path || ""}</span>
              </DetailRow>
              <DetailRow label="User agent">
                <span className="font-mono text-xs">
                  {current.last_user_agent || " (ไม่ได้ส่งมา)"}
                </span>
              </DetailRow>
              <DetailRow label="การบล็อก">
                {current.is_blocked && current.blocked_until
                  ? `บล็อกถึง ${relativeThai(current.blocked_until)}`
                  : "ไม่ถูกบล็อก"}
              </DetailRow>
              <DetailRow label="การตรวจสอบ">
                {REVIEW_LABELS[current.review_state] ?? current.review_state}
                {current.reviewed_by_handle
                  ? ` · โดย @${current.reviewed_by_handle}`
                  : ""}
                {current.note ? ` · ${current.note}` : ""}
              </DetailRow>
            </dl>

            <h3 className="mt-4 mb-2 text-sm font-semibold text-fg">
              หลักฐานล่าสุด ({current.recent_events.length})
            </h3>
            <ul className="space-y-1.5">
              {current.recent_events.map((event) => (
                <li
                  key={event.id}
                  className="rounded border border-edge bg-surface px-2.5 py-2 text-xs"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <LevelBadge level={event.severity} />
                    <span className="font-medium text-fg">
                      {kindLabel(event.kind, event.kind_label)}
                    </span>
                    <span className="ml-auto text-fg-subtle">
                      {relativeThai(event.created_at)}
                    </span>
                  </div>
                  <p className="mt-1 font-mono wrap-break-word text-fg-muted">
                    {event.method} {event.path || ""}
                    {event.status_code ? ` → ${event.status_code}` : ""}
                  </p>
                  {Object.keys(event.detail).length > 0 ? (
                    <p className="mt-0.5 text-fg-subtle">
                      {Object.entries(event.detail)
                        .map(([key, value]) => `${key}: ${value}`)
                        .join(" · ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-sm text-fg-muted">กำลังโหลด…</p>
        )}
      </DetailPanel>
      {confirm.dialog}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Events                                                              */
/* ------------------------------------------------------------------ */

function EventsTab({ vocabulary }: { vocabulary: Vocabulary | null }) {
  const [kind, setKind] = useState("");
  const [severity, setSeverity] = useState("");
  const [since, setSince] = useState("");
  const [search, setSearch] = useState("");
  const debounced = useDebounced(search);

  const list = usePagedList<SecurityEvent>("/admin/security/events/", {
    kind: kind || undefined,
    severity: severity || undefined,
    since_hours: since || undefined,
    search: debounced || undefined,
  });

  const columns: Column<SecurityEvent>[] = [
    {
      key: "created_at",
      header: "เมื่อ",
      render: (row) => (
        <span className="whitespace-nowrap text-xs text-fg-muted">
          {relativeThai(row.created_at)}
        </span>
      ),
    },
    {
      key: "severity",
      header: "ระดับ",
      render: (row) => <LevelBadge level={row.severity} />,
    },
    {
      key: "kind",
      header: "พฤติกรรม",
      render: (row) => kindLabel(row.kind, row.kind_label),
    },
    {
      key: "ip",
      header: "แหล่งที่มา",
      render: (row) => <span className="font-mono text-xs">{row.ip}</span>,
    },
    {
      key: "path",
      header: "เส้นทาง",
      render: (row) => (
        <span className="font-mono text-xs text-fg-muted">
          {row.method} {row.path || ""}
          {row.status_code ? ` → ${row.status_code}` : ""}
        </span>
      ),
    },
    {
      key: "user_agent",
      header: "User agent",
      render: (row) => (
        <span
          title={row.user_agent}
          className="line-clamp-1 max-w-64 font-mono text-xs text-fg-subtle"
        >
          {row.user_agent || " (ไม่ได้ส่งมา)"}
        </span>
      ),
    },
    {
      key: "actor",
      header: "ผู้ใช้",
      render: (row) =>
        row.actor_handle ? (
          <span className="text-xs">@{row.actor_handle}</span>
        ) : (
          <span className="text-xs text-fg-subtle">ไม่ได้ล็อกอิน</span>
        ),
    },
  ];

  return (
    <AdminPanel className="mt-3">
      <DataTableToolbar>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="ค้นหาเส้นทางหรือ user agent"
        />
        <FilterSelect
          label="พฤติกรรม"
          value={kind}
          onChange={setKind}
          options={[
            { value: "", label: "ทั้งหมด" },
            ...(vocabulary?.kinds ?? []).map((option) => ({
              value: option.value,
              label: kindLabel(option.value, option.label),
            })),
          ]}
        />
        <FilterSelect
          label="ระดับ"
          value={severity}
          onChange={setSeverity}
          options={[
            { value: "", label: "ทุกระดับ" },
            ...(vocabulary?.levels ?? []).map((option) => ({
              value: option.value,
              label: LEVEL_LABELS[option.value] ?? option.label,
            })),
          ]}
        />
        <FilterSelect
          label="ช่วงเวลา"
          value={since}
          onChange={setSince}
          options={[
            { value: "", label: "ทั้งหมด" },
            { value: "24", label: "24 ชั่วโมง" },
            { value: "168", label: "7 วัน" },
            { value: "720", label: "30 วัน" },
          ]}
        />
      </DataTableToolbar>

      {list.error ? (
        <ErrorState error={list.error} onRetry={list.refetch} />
      ) : (
        <>
          <DataTable
            caption="บันทึกเหตุการณ์ด้านความปลอดภัย"
            columns={columns}
            rows={list.rows}
            rowKey={(row) => row.id}
            loading={list.loading}
            empty={
              <AdminEmpty
                title="ยังไม่มีเหตุการณ์"
                description="บันทึกนี้เพิ่มอย่างเดียว ลบไม่ได้  เก็บไว้เป็นหลักฐาน"
              />
            }
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
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function AdminSecurityPage() {
  const summary = useSummary();
  const vocabulary = useApiQuery<Vocabulary>(
    (signal) => api.get<Vocabulary>("/admin/security/vocabulary/", { signal }),
    [],
  );

  return (
    <>
      <AdminPageHeader
        title="ความปลอดภัย"
        description="ตรวจจับการสแกน การเรียกไฟล์ลับ และการเข้าถึงแบบอัตโนมัติ พร้อมให้คะแนนและจัดระดับแต่ละแหล่งที่มา"
        actions={
          <Button size="sm" variant="secondary" onClick={() => summary.refetch()}>
            <Icon name="ui/refresh" className="size-4" /> รีเฟรช
          </Button>
        }
      />

      <SummaryStrip summary={summary} />

      <p className="mb-3 flex items-start gap-2 rounded-md border border-edge bg-surface-sunken px-3 py-2 text-xs text-fg-muted">
        <Icon name="ui/info" className="mt-0.5 size-4 shrink-0" />
        <span>
          สัญญาณที่มาจากเบราว์เซอร์ (เช่น &ldquo;เปิด DevTools&rdquo;) เป็นเพียง
          <strong className="font-medium text-fg"> ข้อมูลประกอบ</strong> 
          หน้าเว็บไม่สามารถห้ามเปิด DevTools ได้จริง และสัญญาณเหล่านี้ปลอมได้
          จึงถ่วงน้ำหนักต่ำที่สุด ส่วนการสแกนและการเรียกไฟล์ลับเป็นสิ่งที่เซิร์ฟเวอร์
          เห็นเอง ปลอมไม่ได้
        </span>
      </p>

      <Tabs
        items={[
          {
            key: "sources",
            label: "แหล่งที่มา",
            content: (
              <SourcesTab
                vocabulary={vocabulary.data ?? null}
                onChanged={summary.refetch}
              />
            ),
          },
          {
            key: "events",
            label: "บันทึกเหตุการณ์",
            content: <EventsTab vocabulary={vocabulary.data ?? null} />,
          },
        ]}
      />
    </>
  );
}

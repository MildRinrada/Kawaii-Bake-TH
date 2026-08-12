"use client";

/**
 * กระทู้ถาม-ตอบ - the community question board.
 *
 * Browses `GET /qa/threads/` (visible threads, newest first, real
 * search) and hosts the ask flow: a question targets one recipe or
 * course (`POST /qa/threads/` requires `target_type` + `target_slug`),
 * so the composer includes a live target picker. Answers live on the
 * thread page (`/threads/{id}`) - the path notification links point at.
 * General "how does the platform work" questions belong to the FAQ at
 * `/qa`, not here.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import type {
  Category,
  CourseListItem,
  QaThread,
  RecipeListItem,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { useDebounced } from "@/lib/admin/use-paged-list";
import { useToast } from "@/components/ui/toast";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Icon } from "@/components/ui/icon";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { describeAdminError } from "@/components/admin/lifecycle";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 15;

/** "2 ชม.ที่แล้ว" for anything recent, a date once that stops helping. */
function relativeThai(iso: string): string {
  const then = new Date(iso).getTime();
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 1) return "เมื่อสักครู่";
  if (minutes < 60) return `${minutes} นาทีที่แล้ว`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ชม.ที่แล้ว`;
  const days = Math.round(hours / 24);
  if (days < 8) return `${days} วันที่แล้ว`;
  return new Date(iso).toLocaleDateString("th-TH", { dateStyle: "medium" });
}

/** A question nobody has answered in this long is one the board has
    failed, not one that is merely new (mirrors NEEDS_HELP_AFTER_HOURS). */
const NEEDS_HELP_HOURS = 24;

function needsHelp(thread: QaThread): boolean {
  return (
    thread.answer_count === 0 &&
    Date.now() - new Date(thread.created_at).getTime() >
      NEEDS_HELP_HOURS * 3600_000
  );
}

/** One number in the row's right-hand block. */
function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="min-w-14 text-center">
      <p className="font-display text-lg font-medium text-fg">{value}</p>
      <p className="text-xs text-fg-subtle">{label}</p>
    </div>
  );
}

function StatusBadge({ thread }: { thread: QaThread }) {
  if (thread.accepted_answer) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-success/30 bg-success-subtle px-2.5 py-0.5 text-xs font-medium text-success">
        <Icon name="ui/check-circle" tint className="size-3.5" />
        มีคำตอบที่เลือกแล้ว
      </span>
    );
  }
  if (needsHelp(thread)) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-danger/30 bg-danger-subtle px-2.5 py-0.5 text-xs font-medium text-danger">
        <Icon name="ui/alert" tint className="size-3.5" />
        ต้องการคนช่วยตอบ
      </span>
    );
  }
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-warning/30 bg-warning-subtle px-2.5 py-0.5 text-xs font-medium text-warning">
      <Icon name="ui/clock" tint className="size-3.5" />
      รอคำตอบ
    </span>
  );
}

function ThreadRow({ thread }: { thread: QaThread }) {
  const target = thread.recipe ?? thread.course;
  const targetHref = thread.recipe
    ? `/recipes/${thread.recipe.slug}`
    : thread.course
      ? `/courses/${thread.course.slug}`
      : null;
  const activity = thread.last_answer_at
    ? `ตอบล่าสุด ${relativeThai(thread.last_answer_at)}`
    : `ถามเมื่อ ${relativeThai(thread.created_at)}`;

  return (
    <li>
      <Card className="transition-shadow hover:shadow-overlay">
        <CardBody className="flex items-start gap-3 sm:gap-4">
          {/* The asker's face, not a repeated speech bubble: it says who
              is waiting, and makes the board look inhabited. */}
          <Avatar name={thread.author_handle} size="sm" />

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
              <Link
                href={`/threads/${thread.id}`}
                className="font-medium text-fg hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-focus"
              >
                {thread.title}
              </Link>
              <StatusBadge thread={thread} />
            </div>

            {thread.body ? (
              <p className="mt-0.5 line-clamp-2 text-sm text-fg-muted">
                {thread.body}
              </p>
            ) : target ? (
              // No detail written: say what it is about instead of
              // leaving a gap where a sentence should be.
              <p className="mt-0.5 text-sm text-fg-muted">
                ถามเกี่ยวกับ {thread.recipe ? "สูตร" : "คอร์ส"} “{target.title}”
              </p>
            ) : null}

            <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-subtle">
              <span>โดย @{thread.author_handle}</span>
              <span aria-hidden>·</span>
              <span>{activity}</span>
              {target && targetHref ? (
                <Link
                  href={targetHref}
                  className="rounded-full bg-surface-sunken px-2 py-0.5 hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
                >
                  {thread.recipe ? "สูตร" : "คอร์ส"}: {target.title}
                </Link>
              ) : null}
            </p>
          </div>

          {/* The numbers a reader chooses by, where the eye already goes
              for them  the empty right-hand third of the card. */}
          <div className="flex shrink-0 gap-1 self-center border-l border-edge pl-3 sm:gap-2 sm:pl-4">
            <Stat value={thread.answer_count} label="คำตอบ" />
            <Stat value={thread.view_count} label="คนอ่าน" />
          </div>
        </CardBody>
      </Card>
    </li>
  );
}

/** The ask composer: pick a recipe or course, then ask. */
function AskPanel({
  open,
  onClose,
  onAsked,
}: {
  open: boolean;
  onClose: () => void;
  onAsked: () => void;
}) {
  const router = useRouter();
  const { status } = useAuth();
  const { toast } = useToast();

  const [kind, setKind] = useState<"recipe" | "course">("recipe");
  const [targetSearch, setTargetSearch] = useState("");
  const targetQuery = useDebounced(targetSearch);
  const [targetSlug, setTargetSlug] = useState("");
  const [targetTitle, setTargetTitle] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  const candidates = useApiQuery(
    (signal) =>
      open && !targetSlug
        ? api.get<Paginated<RecipeListItem | CourseListItem>>(
            kind === "recipe" ? "/recipes/" : "/courses/",
            {
              query: {
                search: targetQuery || undefined,
                page_size: 6,
              },
              signal,
            },
          )
        : Promise.resolve(null),
    [open, kind, targetQuery, targetSlug],
  );

  async function ask() {
    if (!targetSlug || !title.trim()) {
      toast("กรุณาเลือกสูตร/คอร์ส และตั้งชื่อคำถามก่อน", "danger");
      return;
    }
    setBusy(true);
    try {
      const thread = await api.post<QaThread>("/qa/threads/", {
        body: {
          target_type: kind,
          target_slug: targetSlug,
          title: title.trim(),
          ...(body.trim() ? { body: body.trim() } : {}),
        },
      });
      toast("โพสต์คำถามแล้ว", "success");
      onAsked();
      router.push(`/threads/${thread.id}`);
    } catch (error) {
      toast(describeAdminError(error), "danger");
      setBusy(false);
    }
  }

  if (!open) return null;

  return (
    <Card>
      <CardBody>
        {status !== "authenticated" ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-fg-muted">
              เข้าสู่ระบบเพื่อตั้งกระทู้ถามชุมชนและผู้สอน
            </p>
            <Link href="/login">
              <Button>เข้าสู่ระบบ</Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-fg">ถามเกี่ยวกับ</p>
              {(
                [
                  { key: "recipe", label: "สูตรขนม" },
                  { key: "course", label: "คอร์สเรียน" },
                ] as const
              ).map((item) => (
                <button
                  key={item.key}
                  type="button"
                  aria-pressed={kind === item.key}
                  onClick={() => {
                    setKind(item.key);
                    setTargetSlug("");
                    setTargetTitle("");
                  }}
                  className={cn(
                    "rounded-full px-3 py-1 text-sm",
                    kind === item.key
                      ? "bg-accent text-fg-inverted"
                      : "bg-surface-sunken text-fg-muted hover:text-fg",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {targetSlug ? (
              <p className="text-sm">
                เลือกแล้ว:{" "}
                <span className="rounded bg-accent-subtle px-2 py-0.5 font-medium">
                  {targetTitle}
                </span>{" "}
                <button
                  type="button"
                  className="text-xs text-fg-muted underline"
                  onClick={() => {
                    setTargetSlug("");
                    setTargetTitle("");
                  }}
                >
                  เปลี่ยน
                </button>
              </p>
            ) : (
              <div className="space-y-1.5">
                <Input
                  type="search"
                  value={targetSearch}
                  placeholder={
                    kind === "recipe" ? "ค้นหาสูตร…" : "ค้นหาคอร์ส…"
                  }
                  aria-label="ค้นหาเป้าหมายคำถาม"
                  onChange={(event) => setTargetSearch(event.target.value)}
                />
                <div className="max-h-40 space-y-1 overflow-y-auto">
                  {candidates.loading ? (
                    <Skeleton className="h-8 w-full rounded" />
                  ) : (
                    (candidates.data?.results ?? []).map((item) => (
                      <button
                        key={item.slug}
                        type="button"
                        onClick={() => {
                          setTargetSlug(item.slug);
                          setTargetTitle(item.title);
                        }}
                        className="block w-full rounded border border-edge bg-surface px-2.5 py-1.5 text-left text-sm hover:border-edge-strong"
                      >
                        {item.title}
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}

            <Field label="คำถาม" required>
              {(control) => (
                <Input
                  {...control}
                  value={title}
                  maxLength={200}
                  placeholder="เช่น ทำไมครัวซองต์ไม่ขึ้นชั้น?"
                  onChange={(event) => setTitle(event.target.value)}
                />
              )}
            </Field>
            <Field label="รายละเอียดเพิ่มเติม">
              {(control) => (
                <Textarea
                  {...control}
                  rows={3}
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                />
              )}
            </Field>
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={onClose}
              >
                ยกเลิก
              </Button>
              <Button size="sm" loading={busy} onClick={ask}>
                โพสต์คำถาม
              </Button>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

/** The board's filter chips. Each one only ever narrows the list. */
const FACETS = [
  { key: "all", label: "ทั้งหมด", query: {} },
  { key: "waiting", label: "รอคำตอบ", query: { resolved: "false" } },
  { key: "resolved", label: "แก้แล้ว", query: { resolved: "true" } },
  { key: "recipe", label: "เกี่ยวกับสูตร", query: { target: "recipe" } },
  { key: "course", label: "เกี่ยวกับคอร์ส", query: { target: "course" } },
] as const;

const SORTS = [
  { value: "latest", label: "ล่าสุด" },
  { value: "active", label: "ตอบล่าสุด" },
  { value: "popular", label: "คนอ่านมากสุด" },
] as const;

export default function ThreadsPage() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [page, setPage] = useState(1);
  const [facet, setFacet] = useState<(typeof FACETS)[number]["key"]>("all");
  const [category, setCategory] = useState("");
  const [ordering, setOrdering] = useState<string>("latest");
  const [asking, setAsking] = useState(false);

  // Any change to what is being asked for resets pagination - the
  // render-time pattern.
  const requestKey = `${search}|${facet}|${category}|${ordering}`;
  const [lastKey, setLastKey] = useState(requestKey);
  if (requestKey !== lastKey) {
    setLastKey(requestKey);
    setPage(1);
  }

  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  const threads = useApiQuery(
    (signal) =>
      api.get<Paginated<QaThread>>("/qa/threads/", {
        query: {
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          category: category || undefined,
          ordering,
          ...(FACETS.find((item) => item.key === facet)?.query ?? {}),
        },
        signal,
      }),
    [page, search, facet, category, ordering],
  );
  const totalPages = Math.max(
    1,
    Math.ceil((threads.data?.count ?? 0) / PAGE_SIZE),
  );
  const results = threads.data?.results ?? [];
  const stranded = results.filter(needsHelp).length;
  const filtered = facet !== "all" || Boolean(category) || Boolean(search);

  return (
    <PageContainer>
      <PageHeader
        title="กระทู้ถาม-ตอบ"
        description="กระทู้จริงจากเพื่อนนักอบ ถามเกี่ยวกับสูตรและคอร์สบนแพลตฟอร์ม — คำถามการใช้งานทั่วไปดูที่คำถามที่พบบ่อยได้เลย"
        actions={
          !asking ? (
            <Button onClick={() => setAsking(true)}>
              <Icon name="ui/plus" tint className="size-4" /> ตั้งกระทู้ถาม
            </Button>
          ) : null
        }
      />

      <div className="space-y-5">
        <AskPanel
          open={asking}
          onClose={() => setAsking(false)}
          onAsked={() => {
            setAsking(false);
            threads.refetch();
          }}
        />

        {/* One search field, full width, with the sort beside it. */}
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="search"
            value={searchInput}
            placeholder="ค้นหากระทู้ เช่น ครัวซองต์…"
            aria-label="ค้นหากระทู้"
            className="min-w-0 flex-1 rounded-full"
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <div className="w-40 shrink-0">
            <Select
              aria-label="เรียงกระทู้"
              value={ordering}
              className="rounded-full"
              onChange={(event) => setOrdering(event.target.value)}
            >
              {SORTS.map((sort) => (
                <option key={sort.value} value={sort.value}>
                  {sort.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <div
          role="group"
          aria-label="กรองกระทู้"
          className="flex flex-wrap items-center gap-2"
        >
          {FACETS.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={facet === item.key}
              onClick={() => setFacet(item.key)}
              className={cn(
                "rounded-full px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-focus",
                facet === item.key
                  ? "bg-fg font-medium text-fg-inverted shadow-raised"
                  : "border border-edge bg-surface text-fg-muted hover:border-edge-strong hover:text-fg",
              )}
            >
              {item.label}
            </button>
          ))}
          <div className="w-44">
            <Select
              aria-label="กรองตามหมวดขนม"
              value={category}
              className="rounded-full py-1.5"
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="">ทุกหมวดขนม</option>
              {(categories.data ?? []).map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name}
                </option>
              ))}
            </Select>
          </div>
          {filtered ? (
            <button
              type="button"
              onClick={() => {
                setFacet("all");
                setCategory("");
                setSearchInput("");
              }}
              className="text-sm text-fg-muted underline hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
            >
              ล้างตัวกรอง
            </button>
          ) : null}
          <span className="ml-auto text-sm text-fg-muted">
            {threads.data ? `${threads.data.count} กระทู้` : ""}
          </span>
        </div>

        {/* The board's own call for help: unanswered questions are the
            thing a Q&A page needs volunteers for. */}
        {stranded > 0 && facet !== "waiting" ? (
          <Card className="border-warning/30 bg-warning-subtle">
            <CardBody className="flex flex-wrap items-center justify-between gap-3 py-3">
              <p className="flex items-center gap-2 text-sm text-fg">
                <Icon name="ui/alert" tint className="size-4 text-warning" />
                มี {stranded} กระทู้ในหน้านี้ที่ยังไม่มีใครตอบเกิน{" "}
                {NEEDS_HELP_HOURS} ชั่วโมง
              </p>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setFacet("waiting")}
              >
                ช่วยตอบกระทู้เหล่านี้
              </Button>
            </CardBody>
          </Card>
        ) : null}

        {threads.loading ? (
          <div className="space-y-3" aria-busy="true">
            <Skeleton className="h-24 w-full rounded-surface" />
            <Skeleton className="h-24 w-full rounded-surface" />
          </div>
        ) : threads.error ? (
          <ErrorState error={threads.error} onRetry={threads.refetch} />
        ) : (threads.data?.results.length ?? 0) === 0 ? (
          <EmptyState
            icon={<Icon name="ui/chat" className="size-8 text-fg-subtle" />}
            title={filtered ? "ไม่พบกระทู้ตามที่กรอง" : "ยังไม่มีกระทู้"}
            description={
              filtered
                ? "ลองล้างตัวกรอง หรือเปลี่ยนคำค้นดู"
                : "เป็นคนแรกที่ตั้งกระทู้ถามเกี่ยวกับสูตรหรือคอร์สได้เลย"
            }
          />
        ) : (
          <>
            <ul className="space-y-3">
              {results.map((thread) => (
                <ThreadRow key={thread.id} thread={thread} />
              ))}
            </ul>
            {totalPages > 1 ? (
              <div className="flex items-center justify-center gap-3">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  ← ก่อนหน้า
                </Button>
                <span className="text-sm text-fg-muted">
                  หน้า {page} / {totalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  ถัดไป →
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </PageContainer>
  );
}

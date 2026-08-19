"use client";

/**
 * The certificate template designer - a visual editor over the design
 * document `PUT /admin/certificates/templates/{slug}/` stores.
 *
 * Layout: element library + layers on the left, the live canvas in the
 * middle, properties of the selection on the right, and a toolbar with
 * course switcher / undo / zoom / preview / publish on top.
 *
 * Two rules shape the state handling:
 *  - History is snapshot-based: pointer gestures mutate the present
 *    document transiently and push ONE history entry on release, so
 *    undo steps match user intentions, not mouse events.
 *  - Saving is autosave (debounced PUT of the draft) and never the same
 *    thing as publishing; "เผยแพร่เทมเพลต" is the only write that
 *    touches the production design.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { api, type Paginated } from "@/lib/api/client";
import type {
  CertificateTemplateDetail,
  CourseListItem,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { relativeThai } from "@/lib/datetime";
import { cn } from "@/lib/cn";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useConfirm } from "@/components/admin/primitives";
import { describeAdminError } from "@/components/admin/lifecycle";
import { CertificateCanvas } from "../../certificate-canvas";
import {
  BLANK_DESIGN,
  BRAND_ASSETS,
  CANVAS_GRID,
  FIELD_KEYS,
  FIELD_LABELS,
  MAX_SIGNATURES,
  SAMPLES,
  freshId,
  makeBox,
  makeField,
  makeImage,
  makeSignature,
  makeText,
  paintOrder,
  signatureCount,
  type DesignDoc,
  type DesignElement,
  type ElementStyle,
} from "../../design-doc";

/* ------------------------------------------------------------------ */
/* History                                                             */
/* ------------------------------------------------------------------ */

const HISTORY_LIMIT = 60;
const SNAP_THRESHOLD = 6;

interface Guides {
  vertical: boolean;
  horizontal: boolean;
}

type Interaction =
  | { mode: "drag"; id: string; startX: number; startY: number; before: DesignDoc }
  | {
      mode: "resize";
      id: string;
      handle: string;
      startX: number;
      startY: number;
      before: DesignDoc;
    }
  | { mode: "rotate"; id: string; before: DesignDoc };

/* ------------------------------------------------------------------ */

export function CertificateDesigner({ slug }: { slug: string }) {
  const { toast } = useToast();
  const confirm = useConfirm();
  const router = useRouter();

  const template = useApiQuery(
    (signal) =>
      api.get<CertificateTemplateDetail>(
        `/admin/certificates/templates/${encodeURIComponent(slug)}/`,
        { signal },
      ),
    [slug],
  );
  const courses = useApiQuery(
    (signal) =>
      api.get<Paginated<CourseListItem>>("/courses/", {
        query: { scope: "all", ordering: "title", page_size: 100 },
        signal,
      }),
    [],
  );

  // ---- document state + history -----------------------------------
  const [doc, setDoc] = useState<DesignDoc | null>(null);
  const [past, setPast] = useState<DesignDoc[]>([]);
  const [future, setFuture] = useState<DesignDoc[]>([]);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoomMode, setZoomMode] = useState<"fit" | number>("fit");
  const [fitScale, setFitScale] = useState(0.6);
  const [guides, setGuides] = useState<Guides>({ vertical: false, horizontal: false });
  const [sampleIndex, setSampleIndex] = useState(0);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "dirty" | "saving" | "saved" | "error">(
    "idle",
  );
  const [publishedAt, setPublishedAt] = useState<string | null>(null);

  const interaction = useRef<Interaction | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Seed editor state when the template arrives (render-time seeding -
  // no setState-in-effect).
  if (template.data && loadedFor !== slug) {
    setLoadedFor(slug);
    setDoc(template.data.draft_design as unknown as DesignDoc);
    setPast([]);
    setFuture([]);
    setSelectedId(null);
    setSaveState("idle");
    setPublishedAt(template.data.published_at ?? null);
  }

  const sample = SAMPLES[sampleIndex] ?? SAMPLES[0];
  const scale = zoomMode === "fit" ? fitScale : zoomMode;
  const selected = doc?.elements.find((element) => element.id === selectedId) ?? null;

  // ---- fit-to-container zoom --------------------------------------
  // Depends on the canvas *size* only: re-measuring on every document
  // edit re-created the observer mid-drag for no reason. The stage also
  // reserves its scrollbar gutter (see className) - without that, the
  // scrollbar appearing shrinks clientWidth, which shrinks the scale,
  // which hides the scrollbar, which grows the scale again: the frame
  // visibly vibrates on resize. The dead-band below absorbs what's left
  // (sub-pixel churn) so the scale never chases its own tail.
  const canvasWidth = doc?.size.width ?? 0;
  const canvasHeight = doc?.size.height ?? 0;
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !canvasWidth || !canvasHeight) return;
    const measure = () => {
      const width = stage.clientWidth - 48;
      const height = stage.clientHeight - 48;
      const next = Math.max(
        0.1,
        Math.min(width / canvasWidth, height / canvasHeight, 1),
      );
      setFitScale((prev) => (Math.abs(prev - next) < 0.005 ? prev : next));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(stage);
    return () => observer.disconnect();
  }, [canvasWidth, canvasHeight]);

  // ---- history helpers --------------------------------------------
  /** Replace the document; `commit` pushes the previous state as one undo step. */
  const update = useCallback(
    (next: DesignDoc, commit: boolean, before?: DesignDoc) => {
      setDoc((current) => {
        if (commit) {
          const snapshot = before ?? current;
          if (snapshot) {
            setPast((stack) => [...stack.slice(-HISTORY_LIMIT), snapshot]);
            setFuture([]);
          }
        }
        return next;
      });
      setSaveState("dirty");
    },
    [],
  );

  function undo() {
    setPast((stack) => {
      const previous = stack[stack.length - 1];
      if (!previous) return stack;
      setDoc((current) => {
        if (current) setFuture((redo) => [...redo, current]);
        return previous;
      });
      setSaveState("dirty");
      return stack.slice(0, -1);
    });
  }

  function redo() {
    setFuture((stack) => {
      const next = stack[stack.length - 1];
      if (!next) return stack;
      setDoc((current) => {
        if (current) setPast((undoStack) => [...undoStack, current]);
        return next;
      });
      setSaveState("dirty");
      return stack.slice(0, -1);
    });
  }

  // ---- autosave ----------------------------------------------------
  useEffect(() => {
    if (!doc || saveState !== "dirty") return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      setSaveState("saving");
      try {
        await api.put(`/admin/certificates/templates/${encodeURIComponent(slug)}/`, {
          body: { design: doc },
        });
        setSaveState("saved");
      } catch {
        setSaveState("error");
      }
    }, 1200);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [doc, saveState, slug]);

  // ---- element ops -------------------------------------------------
  const patchElement = useCallback(
    (id: string, patch: Partial<DesignElement>, commit = true) => {
      if (!doc) return;
      update(
        {
          ...doc,
          elements: doc.elements.map((element) =>
            element.id === id ? { ...element, ...patch } : element,
          ),
        },
        commit,
      );
    },
    [doc, update],
  );

  const patchStyle = useCallback(
    (id: string, patch: Partial<ElementStyle>) => {
      if (!doc) return;
      update(
        {
          ...doc,
          elements: doc.elements.map((element) =>
            element.id === id
              ? { ...element, style: { ...element.style, ...patch } }
              : element,
          ),
        },
        true,
      );
    },
    [doc, update],
  );

  function addElement(element: DesignElement) {
    if (!doc) return;
    const z = Math.max(0, ...doc.elements.map((item) => item.z)) + 1;
    update({ ...doc, elements: [...doc.elements, { ...element, z }] }, true);
    setSelectedId(element.id);
  }

  function removeElement(id: string) {
    if (!doc) return;
    update(
      { ...doc, elements: doc.elements.filter((element) => element.id !== id) },
      true,
    );
    if (selectedId === id) setSelectedId(null);
  }

  function duplicateElement(id: string) {
    if (!doc) return;
    const source = doc.elements.find((element) => element.id === id);
    if (!source) return;
    if (source.kind === "signature" && signatureCount(doc) >= MAX_SIGNATURES) {
      toast(`ลายเซ็นได้สูงสุด ${MAX_SIGNATURES} จุด`, "danger");
      return;
    }
    const copy: DesignElement = {
      ...source,
      id: freshId(source.kind),
      name: `${source.name} (สำเนา)`,
      x: source.x + 24,
      y: source.y + 24,
      z: Math.max(0, ...doc.elements.map((item) => item.z)) + 1,
    };
    update({ ...doc, elements: [...doc.elements, copy] }, true);
    setSelectedId(copy.id);
  }

  function moveLayer(id: string, direction: 1 | -1) {
    if (!doc) return;
    const ordered = paintOrder(doc);
    const index = ordered.findIndex((element) => element.id === id);
    const swap = ordered[index + direction];
    if (!swap) return;
    // Renumber z densely after the swap so ordering stays stable.
    const next = [...ordered];
    [next[index], next[index + direction]] = [next[index + direction], next[index]];
    update(
      {
        ...doc,
        elements: doc.elements.map((element) => ({
          ...element,
          z: next.findIndex((item) => item.id === element.id),
        })),
      },
      true,
    );
  }

  // ---- canvas gestures --------------------------------------------
  function snap(value: number): number {
    return Math.round(value / CANVAS_GRID) * CANVAS_GRID;
  }

  function beginDrag(event: ReactPointerEvent, element: DesignElement) {
    if (element.locked || !doc) return;
    event.preventDefault();
    event.stopPropagation();
    setSelectedId(element.id);
    interaction.current = {
      mode: "drag",
      id: element.id,
      startX: event.clientX,
      startY: event.clientY,
      before: doc,
    };
    (event.target as HTMLElement).setPointerCapture?.(event.pointerId);
  }

  function beginResize(
    event: ReactPointerEvent,
    element: DesignElement,
    handle: string,
  ) {
    if (element.locked || !doc) return;
    event.preventDefault();
    event.stopPropagation();
    interaction.current = {
      mode: "resize",
      id: element.id,
      handle,
      startX: event.clientX,
      startY: event.clientY,
      before: doc,
    };
  }

  function beginRotate(event: ReactPointerEvent, element: DesignElement) {
    if (element.locked || !doc) return;
    event.preventDefault();
    event.stopPropagation();
    interaction.current = { mode: "rotate", id: element.id, before: doc };
  }

  function onStagePointerMove(event: ReactPointerEvent) {
    const act = interaction.current;
    if (!act || !doc) return;
    const before = act.before;
    const source = before.elements.find((element) => element.id === act.id);
    if (!source) return;

    if (act.mode === "drag") {
      const deltaX = (event.clientX - act.startX) / scale;
      const deltaY = (event.clientY - act.startY) / scale;
      let x = snap(source.x + deltaX);
      let y = snap(source.y + deltaY);
      // Center guides: glue the element's centre to the canvas centre.
      const centerX = doc.size.width / 2 - source.w / 2;
      const centerY = doc.size.height / 2 - source.h / 2;
      const nearV = Math.abs(x - centerX) < SNAP_THRESHOLD;
      const nearH = Math.abs(y - centerY) < SNAP_THRESHOLD;
      if (nearV) x = centerX;
      if (nearH) y = centerY;
      setGuides({ vertical: nearV, horizontal: nearH });
      update(
        {
          ...before,
          elements: before.elements.map((element) =>
            element.id === act.id ? { ...element, x, y } : element,
          ),
        },
        false,
      );
    } else if (act.mode === "resize") {
      const deltaX = (event.clientX - act.startX) / scale;
      const deltaY = (event.clientY - act.startY) / scale;
      let { x, y, w, h } = source;
      if (act.handle.includes("e")) w = Math.max(8, snap(source.w + deltaX));
      if (act.handle.includes("s")) h = Math.max(8, snap(source.h + deltaY));
      if (act.handle.includes("w")) {
        w = Math.max(8, snap(source.w - deltaX));
        x = snap(source.x + source.w - w);
      }
      if (act.handle.includes("n")) {
        h = Math.max(8, snap(source.h - deltaY));
        y = snap(source.y + source.h - h);
      }
      update(
        {
          ...before,
          elements: before.elements.map((element) =>
            element.id === act.id ? { ...element, x, y, w, h } : element,
          ),
        },
        false,
      );
    } else {
      // Rotate: angle between pointer and the element's centre.
      const stage = stageRef.current?.querySelector("[data-canvas]");
      const rect = (stage as HTMLElement | null)?.getBoundingClientRect();
      if (!rect) return;
      const centerX = rect.left + (source.x + source.w / 2) * scale;
      const centerY = rect.top + (source.y + source.h / 2) * scale;
      const angle =
        (Math.atan2(event.clientY - centerY, event.clientX - centerX) * 180) /
          Math.PI +
        90;
      const rotation = Math.round(
        event.shiftKey ? Math.round(angle / 15) * 15 : angle,
      );
      update(
        {
          ...before,
          elements: before.elements.map((element) =>
            element.id === act.id ? { ...element, rotation } : element,
          ),
        },
        false,
      );
    }
  }

  function onStagePointerUp() {
    const act = interaction.current;
    if (act && doc) {
      // One undo step per gesture.
      setPast((stack) => [...stack.slice(-HISTORY_LIMIT), act.before]);
      setFuture([]);
      setSaveState("dirty");
    }
    interaction.current = null;
    setGuides({ vertical: false, horizontal: false });
  }

  // ---- keyboard ----------------------------------------------------
  function onKeyDown(event: React.KeyboardEvent) {
    const editingText =
      (event.target as HTMLElement).tagName === "INPUT" ||
      (event.target as HTMLElement).tagName === "TEXTAREA" ||
      (event.target as HTMLElement).tagName === "SELECT";
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      if (event.shiftKey) redo();
      else undo();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
      event.preventDefault();
      redo();
      return;
    }
    if (editingText || !selected || selected.locked) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") {
      event.preventDefault();
      duplicateElement(selected.id);
      return;
    }
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      removeElement(selected.id);
      return;
    }
    const step = event.shiftKey ? 10 : 1;
    const nudge: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    const move = nudge[event.key];
    if (move) {
      event.preventDefault();
      patchElement(selected.id, {
        x: selected.x + move[0],
        y: selected.y + move[1],
      });
    }
  }

  // ---- server verbs ------------------------------------------------
  async function publish() {
    try {
      const result = await api.post<CertificateTemplateDetail>(
        `/admin/certificates/templates/${encodeURIComponent(slug)}/publish/`,
        {},
      );
      setPublishedAt(result.published_at ?? null);
      toast("เผยแพร่เทมเพลตแล้ว - ใช้กับคอร์สนี้ตั้งแต่ตอนนี้", "success");
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  async function resetToPublished() {
    try {
      const result = await api.post<CertificateTemplateDetail>(
        `/admin/certificates/templates/${encodeURIComponent(slug)}/reset/`,
        {},
      );
      setDoc(result.draft_design as unknown as DesignDoc);
      setPast([]);
      setFuture([]);
      setSaveState("saved");
      toast("ย้อนกลับเป็นเวอร์ชันที่เผยแพร่แล้ว", "success");
    } catch (error) {
      toast(describeAdminError(error), "danger");
    }
  }

  const templateMenu = useMemo(
    () => [
      {
        key: "default",
        label: "เริ่มจากเทมเพลตมาตรฐาน KawaiiBake",
        action: async () => {
          await api.delete(
            `/admin/certificates/templates/${encodeURIComponent(slug)}/`,
          );
          template.refetch();
          setLoadedFor(null);
        },
      },
      {
        key: "blank",
        label: "เริ่มจากหน้าว่าง",
        action: async () => {
          update({ ...BLANK_DESIGN }, true);
        },
      },
    ],
    [slug, template, update],
  );

  // ---- render ------------------------------------------------------
  if (template.error) {
    return (
      <div className="p-6">
        <ErrorState error={template.error} onRetry={template.refetch} />
      </div>
    );
  }
  if (!doc) {
    return (
      <div className="space-y-3 p-6" aria-busy="true">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  const courseTitle =
    template.data?.course_title ??
    courses.data?.results.find((course) => course.slug === slug)?.title ??
    slug;
  const signatures = signatureCount(doc);
  const layers = paintOrder(doc).slice().reverse();

  const saveLabel = {
    idle: "พร้อมแก้ไข",
    dirty: "มีการแก้ไขที่ยังไม่บันทึก…",
    saving: "กำลังบันทึก…",
    saved: "บันทึกแล้ว",
    error: "บันทึกไม่สำเร็จ - จะลองใหม่เมื่อแก้ไขอีกครั้ง",
  }[saveState];

  return (
    <div
      className="flex h-[calc(100dvh-3.5rem)] min-h-0 flex-col"
      onKeyDown={onKeyDown}
      tabIndex={-1}
    >
      {/* ---- Toolbar ------------------------------------------------ */}
      <div className="flex flex-wrap items-center gap-2 border-b border-edge bg-surface px-3 py-2">
        <Link
          href="/admin/certificates"
          className="text-sm text-fg-muted hover:text-fg"
        >
          ← เทมเพลตทั้งหมด
        </Link>
        <span className="hidden h-5 w-px bg-edge-strong sm:block" />
        <label className="flex items-center gap-1.5 text-sm text-fg-muted">
          คอร์ส
          <select
            value={slug}
            onChange={(event) => {
              router.push(
                `/admin/certificates/${encodeURIComponent(event.target.value)}/designer` as "/admin/certificates",
              );
            }}
            className="max-w-56 rounded-control border border-edge bg-surface px-2 py-1 text-sm text-fg"
          >
            {(courses.data?.results ?? [{ slug, title: courseTitle }]).map(
              (course) => (
                <option key={course.slug} value={course.slug}>
                  {course.title}
                </option>
              ),
            )}
          </select>
        </label>
        <span className="hidden h-5 w-px bg-edge-strong sm:block" />
        <Button size="sm" variant="secondary" onClick={undo} disabled={past.length === 0}>
          ↶ เลิกทำ
        </Button>
        <Button size="sm" variant="secondary" onClick={redo} disabled={future.length === 0}>
          ↷ ทำซ้ำ
        </Button>
        <label className="flex items-center gap-1.5 text-sm text-fg-muted">
          ซูม
          <select
            value={String(zoomMode)}
            onChange={(event) =>
              setZoomMode(
                event.target.value === "fit"
                  ? "fit"
                  : Number(event.target.value),
              )
            }
            className="rounded-control border border-edge bg-surface px-2 py-1 text-sm text-fg"
          >
            <option value="fit">พอดีจอ</option>
            <option value="0.25">25%</option>
            <option value="0.5">50%</option>
            <option value="0.75">75%</option>
            <option value="1">100%</option>
          </select>
        </label>
        <span
          role="status"
          className={cn(
            "text-xs",
            saveState === "error" ? "text-danger" : "text-fg-subtle",
          )}
        >
          {saveLabel}
        </span>
        <span className="ml-auto flex items-center gap-2">
          <span className="hidden text-xs text-fg-subtle lg:block">
            {publishedAt
              ? `เผยแพร่ล่าสุด ${relativeThai(publishedAt)}`
              : "ยังไม่เคยเผยแพร่ - คอร์สนี้ยังใช้ดีไซน์มาตรฐาน"}
          </span>
          <Button size="sm" variant="secondary" onClick={() => setPreviewOpen(true)}>
            ดูตัวอย่าง
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              confirm.ask({
                title: "ย้อนกลับเป็นเวอร์ชันที่เผยแพร่?",
                body: "แบบร่างปัจจุบันจะถูกแทนที่ด้วยเวอร์ชันที่เผยแพร่ล่าสุด (หรือดีไซน์มาตรฐานถ้ายังไม่เคยเผยแพร่)",
                confirmLabel: "ย้อนกลับ",
                action: resetToPublished,
              })
            }
          >
            รีเซ็ต
          </Button>
          <Button
            size="sm"
            onClick={() =>
              confirm.ask({
                title: "เผยแพร่เทมเพลตนี้?",
                body: `ดีไซน์ปัจจุบันจะกลายเป็นเทมเพลตใบประกาศจริงของ “${courseTitle}”`,
                confirmLabel: "เผยแพร่",
                action: publish,
              })
            }
          >
            เผยแพร่เทมเพลต
          </Button>
        </span>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* ---- Left: library + layers ------------------------------- */}
        <aside className="hidden w-60 shrink-0 flex-col overflow-y-auto border-r border-edge bg-surface md:flex">
          <section className="border-b border-edge p-3">
            <h2 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
              ข้อมูลอัตโนมัติ
            </h2>
            <p className="mt-0.5 text-[11px] text-fg-subtle">
              เติมค่าจริงให้เองตอนออกใบประกาศ
            </p>
            <ul className="mt-2 space-y-1">
              {FIELD_KEYS.map((field) => (
                <li key={field}>
                  <button
                    type="button"
                    onClick={() => addElement(makeField(field))}
                    className="w-full rounded border border-dashed border-edge-strong/60 px-2 py-1 text-left text-xs text-fg-muted hover:border-accent hover:text-fg"
                  >
                    ⊕ {FIELD_LABELS[field]}
                  </button>
                </li>
              ))}
            </ul>
          </section>
          <section className="border-b border-edge p-3">
            <h2 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
              องค์ประกอบดีไซน์
            </h2>
            <div className="mt-2 grid grid-cols-2 gap-1.5">
              <button
                type="button"
                onClick={() => addElement(makeText())}
                className="rounded border border-edge px-2 py-1.5 text-xs text-fg-muted hover:border-accent hover:text-fg"
              >
                ตัวอักษร
              </button>
              <button
                type="button"
                onClick={() => addElement(makeBox())}
                className="rounded border border-edge px-2 py-1.5 text-xs text-fg-muted hover:border-accent hover:text-fg"
              >
                กล่อง/พื้นหลัง
              </button>
              <button
                type="button"
                disabled={signatures >= MAX_SIGNATURES}
                onClick={() => addElement(makeSignature(signatures + 1))}
                className="rounded border border-edge px-2 py-1.5 text-xs text-fg-muted hover:border-accent hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
              >
                ลายเซ็น ({signatures} / {MAX_SIGNATURES})
              </button>
            </div>
            <h3 className="mt-3 text-[11px] font-medium text-fg-subtle">
              รูปภาพและแบรนด์
            </h3>
            <ul className="mt-1.5 space-y-1">
              {BRAND_ASSETS.map((asset) => (
                <li key={asset.src}>
                  <button
                    type="button"
                    onClick={() => addElement(makeImage(asset.src, asset.label))}
                    className="flex w-full items-center gap-2 rounded border border-edge px-2 py-1 text-left text-xs text-fg-muted hover:border-accent hover:text-fg"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element -- curated design asset */}
                    <img src={asset.src} alt="" className="size-6 rounded object-cover" />
                    {asset.label}
                  </button>
                </li>
              ))}
            </ul>
          </section>
          <section className="p-3">
            <h2 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
              เลเยอร์
            </h2>
            <ul className="mt-2 space-y-0.5">
              {layers.map((element) => (
                <li key={element.id}>
                  <div
                    className={cn(
                      "flex items-center gap-1 rounded px-1.5 py-1 text-xs",
                      selectedId === element.id
                        ? "bg-accent-subtle text-fg"
                        : "text-fg-muted hover:bg-surface-sunken",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedId(element.id)}
                      className="min-w-0 flex-1 truncate text-left"
                    >
                      {element.name || element.kind}
                    </button>
                    <button
                      type="button"
                      title="ขึ้น"
                      onClick={() => moveLayer(element.id, 1)}
                      className="px-0.5 hover:text-fg"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      title="ลง"
                      onClick={() => moveLayer(element.id, -1)}
                      className="px-0.5 hover:text-fg"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      title={element.hidden ? "แสดง" : "ซ่อน"}
                      onClick={() =>
                        patchElement(element.id, { hidden: !element.hidden })
                      }
                      className={cn("px-0.5 hover:text-fg", element.hidden && "opacity-40")}
                    >
                      👁
                    </button>
                    <button
                      type="button"
                      title={element.locked ? "ปลดล็อก" : "ล็อก"}
                      onClick={() =>
                        patchElement(element.id, { locked: !element.locked })
                      }
                      className={cn("px-0.5 hover:text-fg", !element.locked && "opacity-40")}
                    >
                      🔒
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-3 space-y-1 border-t border-edge pt-2">
              {templateMenu.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() =>
                    confirm.ask({
                      title: item.label,
                      body: "แบบร่างปัจจุบันจะถูกแทนที่ (ยังเลิกทำได้จนกว่าจะออกจากหน้า)",
                      confirmLabel: "เริ่มใหม่",
                      action: item.action,
                    })
                  }
                  className="w-full rounded px-1.5 py-1 text-left text-[11px] text-fg-subtle hover:bg-surface-sunken hover:text-fg"
                >
                  {item.label}
                </button>
              ))}
            </div>
          </section>
        </aside>

        {/* ---- Center: stage --------------------------------------- */}
        <div
          ref={stageRef}
          className="relative min-w-0 flex-1 overflow-auto bg-surface-sunken p-6 [scrollbar-gutter:stable]"
          onPointerMove={onStagePointerMove}
          onPointerUp={onStagePointerUp}
          onPointerDown={() => setSelectedId(null)}
        >
          <div className="mx-auto w-fit" data-canvas>
            <CertificateCanvas doc={doc} sample={sample} scale={scale}>
              {/* Interaction overlay lives in unscaled design space. */}
              {paintOrder(doc).map((element) =>
                element.hidden ? null : (
                  <div
                    key={`hit-${element.id}`}
                    role="button"
                    aria-label={`เลือก ${element.name}`}
                    tabIndex={0}
                    onPointerDown={(event) => beginDrag(event, element)}
                    onFocus={() => setSelectedId(element.id)}
                    className={cn(
                      "absolute",
                      element.locked ? "cursor-not-allowed" : "cursor-move",
                    )}
                    style={{
                      left: element.x,
                      top: element.y,
                      width: element.w,
                      height: element.h,
                      transform: element.rotation
                        ? `rotate(${element.rotation}deg)`
                        : undefined,
                      zIndex: 900 + element.z,
                    }}
                  >
                    {selectedId === element.id ? (
                      <>
                        <div className="pointer-events-none absolute -inset-px border-2 border-accent" />
                        {!element.locked ? (
                          <>
                            {["nw", "n", "ne", "e", "se", "s", "sw", "w"].map(
                              (handle) => (
                                <span
                                  key={handle}
                                  onPointerDown={(event) =>
                                    beginResize(event, element, handle)
                                  }
                                  className="absolute z-10 size-2.5 rounded-sm border border-accent bg-surface"
                                  style={handleStyle(handle)}
                                />
                              ),
                            )}
                            <span
                              title="หมุน (Shift = ทีละ 15°)"
                              onPointerDown={(event) => beginRotate(event, element)}
                              className="absolute -top-7 left-1/2 z-10 size-3 -translate-x-1/2 cursor-grab rounded-full border border-accent bg-surface"
                            />
                          </>
                        ) : null}
                      </>
                    ) : null}
                  </div>
                ),
              )}
              {guides.vertical ? (
                <div className="pointer-events-none absolute inset-y-0 left-1/2 z-999 w-px bg-accent" />
              ) : null}
              {guides.horizontal ? (
                <div className="pointer-events-none absolute inset-x-0 top-1/2 z-999 h-px bg-accent" />
              ) : null}
            </CertificateCanvas>
          </div>
        </div>

        {/* ---- Right: properties ------------------------------------ */}
        <aside className="hidden w-64 shrink-0 overflow-y-auto border-l border-edge bg-surface lg:block">
          {selected ? (
            <PropertiesPanel
              element={selected}
              doc={doc}
              onPatch={(patch) => patchElement(selected.id, patch)}
              onStyle={(patch) => patchStyle(selected.id, patch)}
              onCenterH={() =>
                patchElement(selected.id, {
                  x: Math.round(doc.size.width / 2 - selected.w / 2),
                })
              }
              onCenterV={() =>
                patchElement(selected.id, {
                  y: Math.round(doc.size.height / 2 - selected.h / 2),
                })
              }
              onForward={() => moveLayer(selected.id, 1)}
              onBackward={() => moveLayer(selected.id, -1)}
              onDuplicate={() => duplicateElement(selected.id)}
              onDelete={() => removeElement(selected.id)}
            />
          ) : (
            <div className="p-4 text-xs text-fg-subtle">
              <p className="font-medium text-fg-muted">ยังไม่ได้เลือกองค์ประกอบ</p>
              <p className="mt-1.5 leading-relaxed">
                คลิกองค์ประกอบบนใบประกาศเพื่อย้าย ปรับขนาด หมุน
                และแก้คุณสมบัติแบบละเอียดที่นี่ - ทุกการแก้ไขเห็นผลทันที
                และระบบบันทึกแบบร่างให้อัตโนมัติ
              </p>
            </div>
          )}
        </aside>
      </div>

      {/* ---- Clean preview ------------------------------------------ */}
      {previewOpen ? (
        <div
          className="fixed inset-0 z-50 flex flex-col bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="ตัวอย่างใบประกาศ"
        >
          <div className="mb-3 flex items-center justify-center gap-2">
            {SAMPLES.map((item, index) => (
              <button
                key={item.label}
                type="button"
                onClick={() => setSampleIndex(index)}
                className={cn(
                  "rounded-full px-3 py-1 text-sm",
                  index === sampleIndex
                    ? "bg-accent text-fg-inverted"
                    : "bg-surface text-fg-muted",
                )}
              >
                {item.label}
              </button>
            ))}
            <Button size="sm" variant="secondary" onClick={() => setPreviewOpen(false)}>
              ปิดตัวอย่าง
            </Button>
          </div>
          <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto">
            <CertificateCanvas
              doc={doc}
              sample={sample}
              scale={Math.min(
                (window.innerWidth - 64) / doc.size.width,
                (window.innerHeight - 120) / doc.size.height,
                1,
              )}
            />
          </div>
        </div>
      ) : null}

      {confirm.dialog}
    </div>
  );
}

function handleStyle(handle: string): CSSProperties {
  const style: CSSProperties = {};
  if (handle.includes("n")) style.top = -5;
  if (handle.includes("s")) style.bottom = -5;
  if (handle.includes("w")) style.left = -5;
  if (handle.includes("e")) style.right = -5;
  if (handle === "n" || handle === "s") {
    style.left = "50%";
    style.marginLeft = -5;
  }
  if (handle === "e" || handle === "w") {
    style.top = "50%";
    style.marginTop = -5;
  }
  style.cursor = `${handle}-resize`;
  return style;
}

/* ------------------------------------------------------------------ */
/* Properties panel                                                    */
/* ------------------------------------------------------------------ */

function NumberField({
  label,
  value,
  onChange,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: number;
}) {
  return (
    <label className="flex items-center justify-between gap-2 text-xs text-fg-muted">
      {label}
      <input
        type="number"
        value={Math.round(value * 100) / 100}
        step={step}
        onChange={(event) => onChange(Number(event.target.value) || 0)}
        className="w-20 rounded-control border border-edge bg-surface px-1.5 py-1 text-right font-mono text-xs text-fg"
      />
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-xs text-fg-muted">
      {label}
      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-0.5 w-full rounded-control border border-edge bg-surface px-1.5 py-1 text-xs text-fg"
      />
    </label>
  );
}

function PropertiesPanel({
  element,
  doc,
  onPatch,
  onStyle,
  onCenterH,
  onCenterV,
  onForward,
  onBackward,
  onDuplicate,
  onDelete,
}: {
  element: DesignElement;
  doc: DesignDoc;
  onPatch: (patch: Partial<DesignElement>) => void;
  onStyle: (patch: Partial<ElementStyle>) => void;
  onCenterH: () => void;
  onCenterV: () => void;
  onForward: () => void;
  onBackward: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const isTextual =
    element.kind === "field" ||
    element.kind === "text" ||
    element.kind === "signature";
  return (
    <div className="space-y-4 p-3">
      <div>
        <TextField
          label="ชื่อเลเยอร์"
          value={element.name}
          onChange={(name) => onPatch({ name })}
        />
        <p className="mt-1 text-[11px] text-fg-subtle">
          {element.kind === "field"
            ? element.text?.trim()
              ? "กำหนดเอง - ทุกใบจะใช้ข้อความที่กรอกแทนข้อมูลจริง"
              : "ข้อมูลอัตโนมัติ - ระบบเติมค่าจริงตอนออกใบประกาศ"
            : "องค์ประกอบดีไซน์ - ตายตัวบนใบประกาศทุกใบ"}
        </p>
      </div>

      <div className="flex flex-wrap gap-1">
        <Button size="sm" variant="secondary" onClick={onCenterH}>
          กึ่งกลาง ↔
        </Button>
        <Button size="sm" variant="secondary" onClick={onCenterV}>
          กึ่งกลาง ↕
        </Button>
        <Button size="sm" variant="secondary" onClick={onForward}>
          ชั้นบน
        </Button>
        <Button size="sm" variant="secondary" onClick={onBackward}>
          ชั้นล่าง
        </Button>
        <Button size="sm" variant="secondary" onClick={onDuplicate}>
          ทำสำเนา
        </Button>
        <Button size="sm" variant="danger" onClick={onDelete}>
          ลบ
        </Button>
      </div>

      <section>
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">
          ตำแหน่งและขนาด
        </h3>
        <div className="mt-1.5 grid grid-cols-2 gap-1.5">
          <NumberField label="X" value={element.x} onChange={(x) => onPatch({ x })} />
          <NumberField label="Y" value={element.y} onChange={(y) => onPatch({ y })} />
          <NumberField
            label="กว้าง"
            value={element.w}
            onChange={(w) => onPatch({ w: Math.max(8, w) })}
          />
          <NumberField
            label="สูง"
            value={element.h}
            onChange={(h) => onPatch({ h: Math.max(8, h) })}
          />
          <NumberField
            label="หมุน°"
            value={element.rotation}
            onChange={(rotation) => onPatch({ rotation })}
          />
          <NumberField
            label="ทึบ"
            value={element.opacity}
            step={0.05}
            onChange={(opacity) =>
              onPatch({ opacity: Math.min(1, Math.max(0, opacity)) })
            }
          />
        </div>
        <p className="mt-1 text-[11px] text-fg-subtle">
          ผืนงาน {doc.size.width}×{doc.size.height}px · ลากบนใบประกาศได้โดยตรง
        </p>
      </section>

      {isTextual ? (
        <section>
          <h3 className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">
            ตัวอักษร
          </h3>
          <div className="mt-1.5 space-y-1.5">
            {element.kind === "text" || element.kind === "field" ? (
              <label className="block text-xs text-fg-muted">
                {element.kind === "field" ? "ข้อความกำหนดเอง" : "ข้อความ"}
                <textarea
                  value={element.text ?? ""}
                  onChange={(event) => onPatch({ text: event.target.value })}
                  rows={2}
                  placeholder={
                    element.kind === "field"
                      ? "เช่น มอบโดย เชฟมิลด์ รินรดา"
                      : undefined
                  }
                  className="mt-0.5 w-full rounded-control border border-edge bg-surface px-1.5 py-1 text-xs text-fg"
                />
                {element.kind === "field" ? (
                  <span className="mt-0.5 block text-[11px] text-fg-subtle">
                    เว้นว่าง = ใช้ข้อมูลจริง
                    {element.field ? ` (${FIELD_LABELS[element.field]})` : ""}
                    {" "}· กรอกเพื่อกำหนดเอง เช่น ชื่อผู้มอบใบประกาศ
                  </span>
                ) : null}
              </label>
            ) : null}
            <label className="flex items-center justify-between gap-2 text-xs text-fg-muted">
              ฟอนต์
              <select
                value={element.style.fontFamily ?? "sans"}
                onChange={(event) =>
                  onStyle({
                    fontFamily: event.target
                      .value as ElementStyle["fontFamily"],
                  })
                }
                className="rounded-control border border-edge bg-surface px-1.5 py-1 text-xs text-fg"
              >
                <option value="sans">มาตรฐาน</option>
                <option value="display">Display</option>
                <option value="serif">Serif</option>
                <option value="mono">Monospace</option>
              </select>
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              <NumberField
                label="ขนาด"
                value={element.style.fontSize ?? 16}
                onChange={(fontSize) => onStyle({ fontSize })}
              />
              <NumberField
                label="น้ำหนัก"
                value={element.style.fontWeight ?? 400}
                step={100}
                onChange={(fontWeight) => onStyle({ fontWeight })}
              />
              <NumberField
                label="บรรทัด"
                value={element.style.lineHeight ?? 1.3}
                step={0.1}
                onChange={(lineHeight) => onStyle({ lineHeight })}
              />
              <NumberField
                label="ช่องไฟ"
                value={element.style.letterSpacing ?? 0}
                step={0.5}
                onChange={(letterSpacing) => onStyle({ letterSpacing })}
              />
            </div>
            <label className="flex items-center justify-between gap-2 text-xs text-fg-muted">
              จัดแนว
              <select
                value={element.style.align ?? "left"}
                onChange={(event) =>
                  onStyle({ align: event.target.value as ElementStyle["align"] })
                }
                className="rounded-control border border-edge bg-surface px-1.5 py-1 text-xs text-fg"
              >
                <option value="left">ชิดซ้าย</option>
                <option value="center">กึ่งกลาง</option>
                <option value="right">ชิดขวา</option>
              </select>
            </label>
            <label className="flex items-center justify-between gap-2 text-xs text-fg-muted">
              สีตัวอักษร
              <input
                type="color"
                value={element.style.color ?? "#3d2c33"}
                onChange={(event) => onStyle({ color: event.target.value })}
                className="h-6 w-10 cursor-pointer rounded border border-edge"
              />
            </label>
          </div>
        </section>
      ) : null}

      {element.kind === "image" ? (
        <section>
          <h3 className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">
            รูปภาพ
          </h3>
          <div className="mt-1.5 space-y-1.5">
            <TextField
              label="URL รูปภาพ"
              value={element.src ?? ""}
              onChange={(src) => onPatch({ src })}
            />
            <label className="flex items-center justify-between gap-2 text-xs text-fg-muted">
              การพอดีกรอบ
              <select
                value={element.style.fit ?? "contain"}
                onChange={(event) =>
                  onStyle({ fit: event.target.value as ElementStyle["fit"] })
                }
                className="rounded-control border border-edge bg-surface px-1.5 py-1 text-xs text-fg"
              >
                <option value="contain">ทั้งภาพ (contain)</option>
                <option value="cover">เต็มกรอบ (cover)</option>
              </select>
            </label>
          </div>
        </section>
      ) : null}

      {element.kind === "signature" && element.signature ? (
        <section>
          <h3 className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">
            ลายเซ็น
          </h3>
          <div className="mt-1.5 space-y-1.5">
            <TextField
              label="ชื่อผู้ลงนาม"
              value={element.signature.name}
              onChange={(name) =>
                onPatch({ signature: { ...element.signature!, name } })
              }
            />
            <TextField
              label="ตำแหน่ง"
              value={element.signature.title}
              onChange={(title) =>
                onPatch({ signature: { ...element.signature!, title } })
              }
            />
            <TextField
              label="องค์กร (ไม่บังคับ)"
              value={element.signature.organization}
              onChange={(organization) =>
                onPatch({ signature: { ...element.signature!, organization } })
              }
            />
            <TextField
              label="URL รูปลายเซ็น (ไม่บังคับ)"
              value={element.signature.image}
              onChange={(image) =>
                onPatch({ signature: { ...element.signature!, image } })
              }
            />
          </div>
        </section>
      ) : null}

      <section>
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">
          พื้นและกรอบ
        </h3>
        <div className="mt-1.5 space-y-1.5">
          <label className="flex items-center justify-between gap-2 text-xs text-fg-muted">
            สีพื้น
            <span className="flex items-center gap-1">
              <input
                type="color"
                value={
                  element.style.background &&
                  element.style.background !== "transparent"
                    ? element.style.background
                    : "#ffffff"
                }
                onChange={(event) => onStyle({ background: event.target.value })}
                className="h-6 w-10 cursor-pointer rounded border border-edge"
              />
              <button
                type="button"
                onClick={() => onStyle({ background: "transparent" })}
                className="rounded border border-edge px-1.5 py-0.5 text-[10px] text-fg-subtle hover:text-fg"
              >
                โปร่งใส
              </button>
            </span>
          </label>
          <div className="grid grid-cols-2 gap-1.5">
            <NumberField
              label="เส้นขอบ"
              value={element.style.borderWidth ?? 0}
              onChange={(borderWidth) =>
                onStyle({ borderWidth: Math.max(0, borderWidth) })
              }
            />
            <NumberField
              label="มุมโค้ง"
              value={element.style.borderRadius ?? 0}
              onChange={(borderRadius) =>
                onStyle({ borderRadius: Math.max(0, borderRadius) })
              }
            />
          </div>
          <label className="flex items-center justify-between gap-2 text-xs text-fg-muted">
            สีเส้นขอบ
            <input
              type="color"
              value={element.style.borderColor ?? "#e7b8c4"}
              onChange={(event) => onStyle({ borderColor: event.target.value })}
              className="h-6 w-10 cursor-pointer rounded border border-edge"
            />
          </label>
          <label className="flex items-center gap-2 text-xs text-fg-muted">
            <input
              type="checkbox"
              checked={element.style.shadow ?? false}
              onChange={(event) => onStyle({ shadow: event.target.checked })}
              className="size-3.5 accent-(--color-accent)"
            />
            เงา
          </label>
        </div>
      </section>
    </div>
  );
}

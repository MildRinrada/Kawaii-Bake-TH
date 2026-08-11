"use client";

/**
 * Legal-document editor - the back office for the `/legal` public page.
 *
 * The writing surface is WYSIWYG: a `contentEditable` region where bold
 * looks bold and lists look like lists *while typing*, driven by a
 * docs-style toolbar. What is **stored** is still the safe RichText text
 * format - the DOM is serialised back to `**bold**` / `- item` markers on
 * every input, so the server, the public renderer and the consent audit
 * trail never see HTML from a browser. The editor is seeded from
 * `richTextToHtml`, which escapes everything and emits only its own
 * tags, so the round trip cannot smuggle markup either way.
 *
 * Saving is explicit, never auto-save: legal text is the one place a
 * half-typed draft must never go live. Each save bumps `version` on the
 * backend, which is how "which text was live when a user consented"
 * stays answerable. The preview button opens the real `/legal` page -
 * the actual thing users see, not an imitation of it.
 */

import { useRef, useState } from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Schemas } from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Field } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminPageHeader } from "@/components/admin/admin-shell";
import { AdminPanel } from "@/components/admin/primitives";
import { richTextToHtml } from "@/components/content/rich-text";
import { cn } from "@/lib/cn";

type LegalDocument = Schemas["LegalDocument"];

const KINDS = ["terms", "privacy", "pdpa", "cookie"] as const;
type Kind = (typeof KINDS)[number];

const KIND_LABELS: Record<Kind, string> = {
  terms: "ข้อตกลงการใช้งาน",
  privacy: "นโยบายความเป็นส่วนตัว",
  pdpa: "ประกาศ PDPA",
  cookie: "นโยบายคุกกี้",
};

function thaiDateTime(iso: string): string {
  return new Date(iso).toLocaleString("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/* ------------------------------------------------------------------ */
/* DOM → RichText serialisation                                        */
/* ------------------------------------------------------------------ */

/** Inline content of one element: text with **`/`*`/`__` marks. */
function serializeInline(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    // Collapse the editor's incidental whitespace, keep real spaces.
    return (node.textContent ?? "").replace(/\s+/g, " ");
  }
  if (!(node instanceof HTMLElement)) return "";
  const inner = Array.from(node.childNodes).map(serializeInline).join("");
  if (!inner.trim()) return inner;
  switch (node.tagName) {
    case "B":
    case "STRONG":
      return `**${inner}**`;
    case "I":
    case "EM":
      return `*${inner}*`;
    case "U":
      return `__${inner}__`;
    case "BR":
      return " ";
    default:
      return inner;
  }
}

/** One block element to its RichText line(s). */
function serializeBlock(el: HTMLElement): string[] {
  switch (el.tagName) {
    case "H1":
    case "H2":
      return [`## ${serializeInline(el).trim()}`];
    case "H3":
    case "H4":
      return [`### ${serializeInline(el).trim()}`];
    case "UL":
      return Array.from(el.querySelectorAll(":scope > li")).map(
        (li) => `- ${serializeInline(li).trim()}`,
      );
    case "OL":
      return Array.from(el.querySelectorAll(":scope > li")).map(
        (li, index) => `${index + 1}. ${serializeInline(li).trim()}`,
      );
    default: {
      // P, DIV and friends. A block that *contains* blocks (browsers nest
      // divs freely while editing) recurses instead of flattening.
      const blockChildren = Array.from(el.children).filter((child) =>
        ["P", "DIV", "H1", "H2", "H3", "H4", "UL", "OL"].includes(child.tagName),
      );
      if (blockChildren.length > 0) {
        return blockChildren.flatMap((child) =>
          serializeBlock(child as HTMLElement),
        );
      }
      const text = serializeInline(el).trim();
      return text ? [text] : [];
    }
  }
}

/** The whole editor back to the stored text format. */
function htmlToRichText(root: HTMLElement): string {
  const blocks: string[] = [];
  for (const child of Array.from(root.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      const text = (child.textContent ?? "").trim();
      if (text) blocks.push(text);
    } else if (child instanceof HTMLElement) {
      blocks.push(...serializeBlock(child));
    }
  }
  return blocks.join("\n\n");
}

/* ------------------------------------------------------------------ */
/* Toolbar - real formatting commands over the contentEditable region  */
/* ------------------------------------------------------------------ */

const TOOLBAR_ACTIONS = [
  { key: "bold", label: "B", title: "ตัวหนา", glyphClass: "font-bold", command: "bold" },
  { key: "italic", label: "I", title: "ตัวเอียง", glyphClass: "italic", command: "italic" },
  { key: "underline", label: "U", title: "ขีดเส้นใต้", glyphClass: "underline", command: "underline" },
  { key: "h2", label: "H2", title: "หัวข้อ", command: "formatBlock", argument: "h2" },
  { key: "h3", label: "H3", title: "หัวข้อย่อย", command: "formatBlock", argument: "h3" },
  { key: "p", label: "¶", title: "ย่อหน้าปกติ", command: "formatBlock", argument: "p" },
  { key: "ul", label: "•", title: "รายการ", command: "insertUnorderedList" },
  { key: "ol", label: "1.", title: "รายการลำดับเลข", command: "insertOrderedList" },
] as const;

function FormatToolbar({ onCommand }: { onCommand: () => void }) {
  return (
    <div
      role="toolbar"
      aria-label="เครื่องมือจัดรูปแบบ"
      className="flex flex-wrap items-center gap-1 rounded-t-control border border-b-0 border-edge-strong/50 bg-surface-sunken px-2 py-1.5"
    >
      {TOOLBAR_ACTIONS.map((action) => (
        <button
          key={action.key}
          type="button"
          title={action.title}
          aria-label={action.title}
          // `preventDefault` on mousedown keeps the text selection alive -
          // a normal click would move focus and collapse it first.
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            document.execCommand(
              action.command,
              false,
              "argument" in action ? action.argument : undefined,
            );
            onCommand();
          }}
          className={cn(
            "flex h-8 min-w-8 items-center justify-center rounded-control px-2 text-sm text-fg-muted",
            "hover:bg-surface hover:text-fg focus-visible:outline-2 focus-visible:outline-focus",
            "glyphClass" in action ? action.glyphClass : undefined,
          )}
        >
          {action.label}
        </button>
      ))}
      <span className="ml-auto hidden text-[11px] text-fg-subtle sm:block">
        เลือกข้อความแล้วกดปุ่ม - เห็นผลทันทีขณะพิมพ์
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Editor                                                              */
/* ------------------------------------------------------------------ */

function DocumentEditor({ kind }: { kind: Kind }) {
  const { toast } = useToast();
  const query = useApiQuery(
    (signal) => api.get<LegalDocument>(`/legal/${kind}/`, { signal }),
    [kind],
  );

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const editorRef = useRef<HTMLDivElement>(null);

  // Seed once per loaded document version - derived during render. The
  // contentEditable's HTML is set via dangerouslySetInnerHTML exactly at
  // seed time (keyed below), then the browser owns the DOM; React never
  // re-renders into it while the admin is typing.
  const [seededFor, setSeededFor] = useState<string | null>(null);
  // Frozen at seed time: if this string changed on every keystroke,
  // React would rewrite innerHTML each render and destroy the caret.
  const [seedHtml, setSeedHtml] = useState("");
  // Bumped by "ยกเลิกการแก้ไข" so the editor remounts even when the
  // server copy (and therefore seedKey) is unchanged.
  const [seedNonce, setSeedNonce] = useState(0);
  const seedKey = query.data ? `${kind}:${query.data.version}:${seedNonce}` : null;
  if (query.data && seededFor !== seedKey) {
    setSeededFor(seedKey);
    setTitle(query.data.title);
    setBody(query.data.body);
    setSeedHtml(richTextToHtml(query.data.body));
  }

  const dirty =
    query.data != null &&
    (title !== query.data.title || body !== query.data.body);

  function syncFromEditor() {
    if (editorRef.current) setBody(htmlToRichText(editorRef.current));
  }

  async function save() {
    if (!dirty || !query.data) return;
    setSaving(true);
    try {
      // Send only what changed; the backend refuses an empty patch.
      const patch: Record<string, string> = {};
      if (title !== query.data.title) patch.title = title;
      if (body !== query.data.body) patch.body = body;
      await api.patch(`/legal/${kind}/`, { body: patch });
      toast(`บันทึก${KIND_LABELS[kind]}แล้ว - ประกาศใช้ทันที`, "success");
      query.refetch();
    } catch (error) {
      toast(
        error instanceof ApiError ? error.message : "บันทึกไม่สำเร็จ",
        "danger",
      );
    } finally {
      setSaving(false);
    }
  }

  if (query.loading) {
    return (
      <div aria-busy="true" className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (query.error || !query.data) {
    return <ErrorState error={query.error} onRetry={query.refetch} />;
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-fg-subtle">
        ฉบับที่ {query.data.version} · แก้ไขล่าสุด{" "}
        {thaiDateTime(query.data.updated_at)} · ผู้ใช้เห็นข้อความนี้ที่หน้า{" "}
        <span className="font-mono">/legal</span> ทันทีที่บันทึก
      </p>

      <Field label="หัวข้อเอกสาร" required>
        {(control) => (
          <Input
            {...control}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        )}
      </Field>

      <div>
        <p className="mb-1.5 block text-sm font-medium text-fg">
          เนื้อหา
          <span aria-hidden className="font-semibold text-danger">
            {" "}
            *
          </span>
        </p>
        <FormatToolbar onCommand={syncFromEditor} />
        <div
          ref={editorRef}
          key={seedKey}
          contentEditable
          suppressContentEditableWarning
          role="textbox"
          aria-multiline="true"
          aria-label="เนื้อหาเอกสาร"
          onInput={syncFromEditor}
          onBlur={syncFromEditor}
          // Seeded from our own escaping serialiser - see file docstring.
          dangerouslySetInnerHTML={{ __html: seedHtml }}
          className={cn(
            "min-h-96 rounded-b-control border border-edge-strong/50 bg-surface px-5 py-4",
            "text-[0.95rem] leading-relaxed text-fg",
            "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus",
            // Match the public renderer's shapes so WYSIWYG is honest.
            "[&_h2]:font-display [&_h2]:pt-2 [&_h2]:text-lg [&_h2]:font-medium",
            "[&_h3]:pt-1 [&_h3]:text-base [&_h3]:font-semibold",
            "[&_p]:my-3 first:[&_p]:mt-0",
            "[&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:marker:text-accent",
            "[&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:marker:text-accent",
            "[&_li]:my-1",
          )}
        />
      </div>

      <div className="flex flex-wrap items-center justify-end gap-2">
        <a
          href={`/legal?doc=${kind}`}
          target="_blank"
          rel="noreferrer"
          className="mr-auto"
        >
          <Button type="button" variant="ghost">
            <Icon name="ui/eye" className="size-4" />
            ดูหน้าจริง /legal
          </Button>
        </a>
        {dirty ? (
          <Button
            variant="secondary"
            disabled={saving}
            onClick={() => {
              // Remount the editor, re-seeded from the server copy.
              setSeedNonce((nonce) => nonce + 1);
            }}
          >
            ยกเลิกการแก้ไข
          </Button>
        ) : null}
        <Button loading={saving} disabled={!dirty} onClick={() => void save()}>
          บันทึกและประกาศใช้ (ฉบับที่ {query.data.version + 1})
        </Button>
      </div>
    </div>
  );
}

export default function AdminLegalPage() {
  const [current, setCurrent] = useState<Kind>("terms");

  return (
    <>
      <AdminPageHeader
        title="ข้อตกลงและนโยบาย"
        description="แก้ไขเอกสารทางกฎหมายทั้งสี่ฉบับ - ทุกการบันทึกจะเพิ่มเลขฉบับและประกาศใช้ทันที"
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {KINDS.map((kind) => (
          <button
            key={kind}
            type="button"
            aria-pressed={kind === current}
            onClick={() => setCurrent(kind)}
            className={cn(
              "rounded-full px-4 py-2 text-sm transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
              kind === current
                ? "bg-accent font-medium text-fg-inverted shadow-raised"
                : "bg-surface text-fg-muted shadow-raised hover:text-fg",
            )}
          >
            {KIND_LABELS[kind]}
          </button>
        ))}
      </div>

      <AdminPanel>
        <div className="px-4 py-4 sm:px-5">
          {/* Keyed so switching documents never leaks a half-edited draft
              from one document into another. */}
          <DocumentEditor key={current} kind={current} />
        </div>
      </AdminPanel>
    </>
  );
}

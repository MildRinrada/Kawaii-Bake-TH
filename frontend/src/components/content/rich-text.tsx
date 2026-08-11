/**
 * RichText - the document formatting the legal pages support.
 *
 * A deliberately tiny markdown subset, parsed into React elements and
 * never into HTML, so the admin editor can never become an injection
 * vector into a public page:
 *
 *   ## หัวข้อ          → section heading
 *   ### หัวข้อย่อย      → sub-heading
 *   - รายการ           → bullet list (consecutive lines group)
 *   1. รายการ          → numbered list (consecutive lines group)
 *   **ตัวหนา**          → bold
 *   *ตัวเอียง*          → italic
 *   __ขีดเส้นใต้__       → underline
 *
 * Everything else is a paragraph; blank lines separate blocks. Unknown
 * syntax renders as the literal characters typed - a parser that guesses
 * is worse than one that shows you what you wrote.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/* ------------------------------------------------------------------ */
/* Inline: **bold**, *italic*, __underline__                           */
/* ------------------------------------------------------------------ */

const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*)/g;

function renderInline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={index} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("__") && part.endsWith("__") && part.length > 4) {
      return (
        <u key={index} className="underline underline-offset-2">
          {part.slice(2, -2)}
        </u>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

/* ------------------------------------------------------------------ */
/* Blocks                                                              */
/* ------------------------------------------------------------------ */

type Block =
  | { type: "h2" | "h3" | "p"; text: string }
  | { type: "ul" | "ol"; items: string[] };

function parseBlocks(body: string): Block[] {
  const blocks: Block[] = [];

  /** The list being accumulated, if the previous line was a list item. */
  const openList = (): Block | undefined => blocks[blocks.length - 1];

  // Split on blank lines first; a block may still contain list lines.
  for (const chunk of body.split(/\n\s*\n/)) {
    const lines = chunk.split("\n").map((line) => line.trim()).filter(Boolean);
    // A blank line always ends a list, so mark the boundary.
    let continuing = false;

    for (const line of lines) {
      if (line.startsWith("### ")) {
        blocks.push({ type: "h3", text: line.slice(4) });
        continuing = false;
      } else if (line.startsWith("## ")) {
        blocks.push({ type: "h2", text: line.slice(3) });
        continuing = false;
      } else if (/^[-•]\s+/.test(line)) {
        const last = openList();
        const item = line.replace(/^[-•]\s+/, "");
        if (continuing && last?.type === "ul") last.items.push(item);
        else blocks.push({ type: "ul", items: [item] });
        continuing = true;
      } else if (/^\d+[.)]\s+/.test(line)) {
        const last = openList();
        const item = line.replace(/^\d+[.)]\s+/, "");
        if (continuing && last?.type === "ol") last.items.push(item);
        else blocks.push({ type: "ol", items: [item] });
        continuing = true;
      } else {
        blocks.push({ type: "p", text: line });
        continuing = false;
      }
    }
  }
  return blocks;
}

/* ------------------------------------------------------------------ */
/* HTML generation - for the admin's WYSIWYG editor seed               */
/* ------------------------------------------------------------------ */

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function inlineHtml(text: string): string {
  return text
    .split(INLINE)
    .map((part) => {
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
        return `<strong>${escapeHtml(part.slice(2, -2))}</strong>`;
      }
      if (part.startsWith("__") && part.endsWith("__") && part.length > 4) {
        return `<u>${escapeHtml(part.slice(2, -2))}</u>`;
      }
      if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        return `<em>${escapeHtml(part.slice(1, -1))}</em>`;
      }
      return escapeHtml(part);
    })
    .join("");
}

/**
 * Render a RichText body to an HTML string for a `contentEditable`
 * editor seed. Safe by construction: every character of the input is
 * escaped and the only tags in the output are the ones this function
 * writes - the input has no way to smuggle markup through.
 */
export function richTextToHtml(body: string): string {
  return parseBlocks(body)
    .map((block) => {
      switch (block.type) {
        case "h2":
          return `<h2>${inlineHtml(block.text)}</h2>`;
        case "h3":
          return `<h3>${inlineHtml(block.text)}</h3>`;
        case "ul":
          return `<ul>${block.items.map((item) => `<li>${inlineHtml(item)}</li>`).join("")}</ul>`;
        case "ol":
          return `<ol>${block.items.map((item) => `<li>${inlineHtml(item)}</li>`).join("")}</ol>`;
        default:
          return `<p>${inlineHtml(block.text)}</p>`;
      }
    })
    .join("");
}

export function RichText({
  body,
  className,
}: {
  body: string;
  className?: string;
}) {
  return (
    <div className={cn("space-y-4", className)}>
      {parseBlocks(body).map((block, index) => {
        switch (block.type) {
          case "h2":
            return (
              <h2
                key={index}
                className="font-display pt-2 text-lg font-medium text-fg"
              >
                {renderInline(block.text)}
              </h2>
            );
          case "h3":
            return (
              <h3 key={index} className="pt-1 text-base font-semibold text-fg">
                {renderInline(block.text)}
              </h3>
            );
          case "ul":
            return (
              <ul
                key={index}
                className="list-disc space-y-1.5 pl-6 text-[0.95rem] leading-relaxed text-fg marker:text-accent"
              >
                {block.items.map((item, i) => (
                  <li key={i}>{renderInline(item)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol
                key={index}
                className="list-decimal space-y-1.5 pl-6 text-[0.95rem] leading-relaxed text-fg marker:font-medium marker:text-accent"
              >
                {block.items.map((item, i) => (
                  <li key={i}>{renderInline(item)}</li>
                ))}
              </ol>
            );
          default:
            return (
              <p
                key={index}
                className="text-[0.95rem] leading-relaxed text-fg"
              >
                {renderInline(block.text)}
              </p>
            );
        }
      })}
    </div>
  );
}

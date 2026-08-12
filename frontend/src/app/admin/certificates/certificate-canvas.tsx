"use client";

/**
 * The pure certificate renderer: one design document + one sample-data
 * set → the certificate, at any scale. Used by the editor canvas (with
 * an interaction overlay on top) and by the clean preview (alone).
 *
 * Everything is typed style values on React elements — a document has
 * no way to produce markup.
 */

import type { CSSProperties } from "react";

import { cn } from "@/lib/cn";
import {
  paintOrder,
  type DesignDoc,
  type DesignElement,
  type SampleData,
} from "./design-doc";

const FONT_CLASS: Record<string, string> = {
  display: "font-display",
  serif: "font-serif",
  mono: "font-mono",
  sans: "",
};

function elementBoxStyle(element: DesignElement): CSSProperties {
  return {
    position: "absolute",
    left: element.x,
    top: element.y,
    width: element.w,
    height: element.h,
    transform: element.rotation ? `rotate(${element.rotation}deg)` : undefined,
    opacity: element.opacity,
    zIndex: element.z,
  };
}

function textStyle(element: DesignElement): CSSProperties {
  const style = element.style;
  return {
    fontSize: style.fontSize,
    fontWeight: style.fontWeight,
    lineHeight: style.lineHeight,
    letterSpacing: style.letterSpacing,
    textAlign: style.align,
    color: style.color,
    background: style.background,
    borderRadius: style.borderRadius,
  };
}

function frameStyle(element: DesignElement): CSSProperties {
  const style = element.style;
  return {
    background: style.background,
    borderStyle: style.borderWidth ? "solid" : undefined,
    borderWidth: style.borderWidth,
    borderColor: style.borderColor,
    borderRadius: style.borderRadius,
    boxShadow: style.shadow ? "0 8px 24px rgba(61, 44, 51, 0.18)" : undefined,
  };
}

export function ElementContent({
  element,
  sample,
}: {
  element: DesignElement;
  sample: SampleData;
}) {
  if (element.kind === "box") {
    return <div className="size-full" style={frameStyle(element)} />;
  }
  if (element.kind === "image") {
    return element.src ? (
      // eslint-disable-next-line @next/next/no-img-element -- design asset chosen by staff
      <img
        src={element.src}
        alt=""
        draggable={false}
        className="size-full"
        style={{
          objectFit: element.style.fit ?? "contain",
          borderRadius: element.style.borderRadius,
          boxShadow: element.style.shadow
            ? "0 8px 24px rgba(61, 44, 51, 0.18)"
            : undefined,
        }}
      />
    ) : (
      <div className="flex size-full items-center justify-center rounded border border-dashed border-edge-strong text-xs text-fg-subtle">
        เลือกรูปภาพ
      </div>
    );
  }
  if (element.kind === "signature") {
    const signature = element.signature;
    return (
      <div
        className={cn(
          "flex size-full flex-col justify-end",
          FONT_CLASS[element.style.fontFamily ?? "sans"],
        )}
        style={{ ...textStyle(element), ...frameStyle(element) }}
      >
        {signature?.image ? (
          // eslint-disable-next-line @next/next/no-img-element -- design asset chosen by staff
          <img
            src={signature.image}
            alt=""
            draggable={false}
            className="mx-auto mb-1 h-1/2 object-contain"
          />
        ) : (
          <div className="mx-auto mb-1 h-1/2 w-3/4 border-b border-current opacity-60" />
        )}
        <p className="leading-tight">{signature?.name || "ชื่อผู้ลงนาม"}</p>
        {signature?.title ? (
          <p className="text-[0.8em] leading-tight opacity-75">
            {signature.title}
          </p>
        ) : null}
        {signature?.organization ? (
          <p className="text-[0.8em] leading-tight opacity-60">
            {signature.organization}
          </p>
        ) : null}
      </div>
    );
  }
  // field | text — a line (or block) of typography. A field with a
  // non-blank `text` is a staff override ("มอบโดย เชฟมิลด์"): it wins
  // over the automatic value on every certificate.
  const value =
    element.kind === "field" && element.field
      ? element.text?.trim()
        ? element.text
        : sample.values[element.field]
      : (element.text ?? "");
  return (
    <div
      className={cn(
        "flex size-full flex-col justify-center whitespace-pre-wrap",
        FONT_CLASS[element.style.fontFamily ?? "sans"],
      )}
      style={textStyle(element)}
    >
      <span className="w-full">{value}</span>
    </div>
  );
}

/**
 * The certificate itself. `scale` shrinks the fixed design space to fit
 * a container while keeping every coordinate true.
 */
export function CertificateCanvas({
  doc,
  sample,
  scale = 1,
  className,
  children,
}: {
  doc: DesignDoc;
  sample: SampleData;
  scale?: number;
  className?: string;
  /** Editor overlay (selection chrome), rendered inside the scaled space. */
  children?: React.ReactNode;
}) {
  return (
    <div
      className={className}
      style={{
        width: doc.size.width * scale,
        height: doc.size.height * scale,
      }}
    >
      <div
        className="relative origin-top-left shadow-overlay"
        style={{
          width: doc.size.width,
          height: doc.size.height,
          transform: `scale(${scale})`,
          background: doc.background,
        }}
      >
        {paintOrder(doc).map((element) =>
          element.hidden ? null : (
            <div key={element.id} style={elementBoxStyle(element)}>
              <ElementContent element={element} sample={sample} />
            </div>
          ),
        )}
        {children}
      </div>
    </div>
  );
}

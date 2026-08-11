import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export type Tone =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "berry"
  | "peach"
  | "butter"
  | "lavender"
  | "mint";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-sunken text-fg-muted",
  success: "bg-success-subtle text-success",
  warning: "bg-warning-subtle text-warning",
  danger: "bg-danger-subtle text-danger",
  berry: "bg-berry-soft text-berry-ink",
  peach: "bg-peach-soft text-peach-ink",
  butter: "bg-butter-soft text-butter-ink",
  lavender: "bg-lavender-soft text-lavender-ink",
  mint: "bg-mint-soft text-mint-ink",
};

/** Soft pill badge. Flavor tones carry the platform's category language. */
export function Badge({
  tone = "neutral",
  className,
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
      {...rest}
    />
  );
}

/** Deterministic flavor for a category slug  stable, coordinated colors. */
const FLAVOR_CYCLE: Tone[] = ["berry", "peach", "butter", "lavender", "mint"];

export function flavorFor(slug: string): Tone {
  let hash = 0;
  for (const char of slug) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  return FLAVOR_CYCLE[hash % FLAVOR_CYCLE.length];
}

/** Difficulty gets fixed semantics: easy=mint … expert=berry. */
const DIFFICULTY_TONES: Record<string, Tone> = {
  easy: "mint",
  medium: "butter",
  hard: "peach",
  expert: "berry",
  // Course difficulty scale
  beginner: "mint",
  intermediate: "butter",
  advanced: "peach",
};

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "ง่าย",
  medium: "ปานกลาง",
  hard: "ยาก",
  expert: "ขั้นสูง",
  beginner: "เริ่มต้นได้เลย",
  intermediate: "ระดับกลาง",
  advanced: "ขั้นสูง",
};

export function DifficultyBadge({ level }: { level: string }) {
  return (
    <Badge tone={DIFFICULTY_TONES[level] ?? "neutral"}>
      {DIFFICULTY_LABELS[level] ?? level}
    </Badge>
  );
}

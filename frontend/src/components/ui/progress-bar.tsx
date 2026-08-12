import { cn } from "@/lib/cn";

/** Accessible completion bar  mint fill on a sunken track. */
export function ProgressBar({
  percent,
  label = "ความคืบหน้า",
  className,
}: {
  percent: number;
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className={cn(
        // The track must be visible on its own: at 0% the fill has no
        // width, and a bar you cannot see reads as a broken component
        // rather than as "not started yet".
        "h-3 w-full overflow-hidden rounded-full bg-surface-sunken",
        className,
      )}
    >
      <div
        className="h-full rounded-full bg-mint-ink/70 transition-[width] duration-300"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

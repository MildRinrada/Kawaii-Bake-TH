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
        "h-3 w-full overflow-hidden ",
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

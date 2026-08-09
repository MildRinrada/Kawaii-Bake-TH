import Link from "next/link";

/**
 * Auth screens live outside the app chrome: a centered column with just
 * a way home. Visual treatment comes later.
 */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <Link
        href="/"
        className="mb-6 text-sm font-semibold text-fg focus-visible:outline-2 focus-visible:outline-focus"
      >
        KawaiiBake
      </Link>
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}

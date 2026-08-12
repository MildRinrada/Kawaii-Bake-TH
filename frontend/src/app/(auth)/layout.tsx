import Link from "next/link";

import { ArtIcon, Icon } from "@/components/ui/icon";
import { BRAND_MARK } from "@/lib/assets";

/**
 * Auth screens live outside the app chrome, so the way back has to be
 * explicit: the mark is the same one the header carries elsewhere (a
 * logo people already read as "home"), and the worded link beside it
 * says so for anyone who does not.
 *
 * The column width belongs to the page, not to this file  sign-in is a
 * narrow card, sign-up is a two-column pitch.
 */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-dvh flex-col px-4 py-6 sm:px-6">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4">
        <Link
          href="/"
          aria-label="KawaiiBake  กลับหน้าแรก"
          className="font-display flex items-center gap-2 text-lg font-medium text-fg focus-visible:outline-2 focus-visible:outline-focus"
        >
          <ArtIcon src={BRAND_MARK} className="size-10" />
          <span>
            Kawaii<span className="text-accent">Bake</span>
          </span>
        </Link>
        <Link
          href="/"
          className="flex items-center gap-1 rounded-control px-2 py-1 text-sm text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
        >
          <Icon name="ui/arrow-left" tint className="size-4" />
          กลับหน้าแรก
        </Link>
      </header>
      <main className="flex flex-1 items-center justify-center py-8">
        {children}
      </main>
    </div>
  );
}

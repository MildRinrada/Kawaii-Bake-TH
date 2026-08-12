"use client";

/**
 * The photographic column every auth screen shares.
 *
 * One component so sign-in, sign-up and the two recovery screens are
 * visibly the same place - and so the heading is at the *top* of the
 * column, level with the first thing to fill in, rather than floating
 * near the bottom where the eye reaches it last.
 *
 * Below `lg` the photograph is dropped and only the words remain: on a
 * phone the column is what someone scrolls past to reach the form, and
 * a full-bleed picture there just pushes the fields off screen.
 */

import { Icon, type UiIconName } from "@/components/ui/icon";
import { categoryArt } from "@/lib/assets";

export interface AuthPoint {
  icon: UiIconName;
  title: string;
  body: string;
}

export function AuthAside({
  title,
  lead,
  points,
  photo,
  animateKey,
}: {
  title: string;
  lead: string;
  points: AuthPoint[];
  /** A `categoryArt` slug - different per screen, so a switch is visible. */
  photo: string;
  /** Changing this replays the entrance animation (the slider uses it). */
  animateKey?: string;
}) {
  return (
    <aside className="relative overflow-hidden lg:rounded-surface lg:border lg:border-edge">
      {/* eslint-disable-next-line @next/next/no-img-element -- local static
          asset; next/image buys nothing for a fixed frame */}
      <img
        key={photo}
        src={categoryArt(photo)}
        alt=""
        className="kb-auth-swap absolute inset-0 hidden size-full object-cover lg:block"
      />
      {/* Scrim, heaviest where the words are: the copy has to hold AA over
          a photograph, and the photograph has to stay recognisable below
          it. */}
      <div
        aria-hidden
        className="absolute inset-0 hidden bg-linear-to-b from-black/78 via-black/52 to-black/20 lg:block"
      />
      <div className="relative flex h-full flex-col gap-5 lg:p-7">
        <div className="space-y-1.5">
          {/* Keyed on the text: React replaces the node when the screen
              changes, which is what re-runs the entrance animation. */}
          <h1
            key={animateKey ?? title}
            className="font-display kb-auth-swap text-2xl font-medium text-fg sm:text-3xl lg:text-fg-inverted"
          >
            {title}
          </h1>
          <p className="text-sm text-fg-muted lg:text-fg-inverted/80">{lead}</p>
        </div>
        <ul className="space-y-3">
          {points.map((point) => (
            <li key={point.title} className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-berry-soft text-berry-ink lg:bg-white/15 lg:text-fg-inverted">
                <Icon name={`ui/${point.icon}`} tint className="size-4.5" />
              </span>
              <span>
                <span className="block text-sm font-medium text-fg lg:text-fg-inverted">
                  {point.title}
                </span>
                <span className="block text-sm text-fg-muted lg:text-fg-inverted/80">
                  {point.body}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

/** The shared two-column frame: pitch on the left, one card on the right. */
export function AuthLayout({
  aside,
  children,
}: {
  aside: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="grid w-full max-w-4xl gap-8 lg:grid-cols-[1fr_25rem] lg:gap-12">
      {aside}
      {children}
    </div>
  );
}

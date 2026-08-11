/**
 * Paths into the static asset library under `public/`.
 *
 * Components import from here rather than typing `/icons/...` string
 * literals, so a folder move is one edit and a missing file is a
 * grep away. See `public/README.md` for the folder contract.
 */

/** Full-colour status art for dialogs and result screens. */
export const MODAL_ART = {
  success: "/icons/modal/success.svg",
  error: "/icons/modal/error.svg",
  warning: "/icons/modal/warning.svg",
  info: "/icons/modal/info.svg",
  confirmDelete: "/icons/modal/confirm-delete.svg",
  locked: "/icons/modal/locked.svg",
} as const;

/**
 * Category photography for one `RecipeCategory.slug`.
 *
 * `cake_decorating` / `vegan` / `gluten_free` were retired (deactivated
 * server-side, not deleted) because they describe a technique or a diet
 * that cuts across every other category rather than sitting beside them
 *  a macaron can be vegan, a cake can be decorated. They no longer come
 * back from `/recipe-categories/`, so they never reach this map.
 *
 * An unknown slug (a category an admin adds later, or a recipe left
 * genuinely uncategorised) resolves to `other.svg`  a real "ไม่แน่ใจว่า
 * เข้าหมวดไหน" bucket, not a broken image.
 */
const CATEGORY_PHOTOS: Record<string, string> = {
  bread: "/category/bread.jpg",
  cake: "/category/cake.jpg",
  cookies: "/category/cookies.jpg",
  pastry: "/category/pastry.jpg",
  pie: "/category/pie_tart.jpg",
  macaron: "/category/macarons.jpg",
  chocolate: "/category/chocolate.jpg",
};

export const CATEGORY_OTHER_PHOTO = "/category/other.svg";

export function categoryArt(slug: string): string {
  return CATEGORY_PHOTOS[slug] ?? CATEGORY_OTHER_PHOTO;
}

/**
 * Small flat-colour category glyphs (bread, cake, cookies, …) for inline
 * chips and pills  where `categoryArt`'s cropped photo would be too much
 * detail at 20px. Same slug set as `CATEGORY_PHOTOS`; an unknown slug
 * falls back to the same "other" bucket art used for photos.
 */
const CATEGORY_ICONS: Record<string, string> = {
  bread: "/icons/category/bread.svg",
  cake: "/icons/category/cake.svg",
  cookies: "/icons/category/cookies.svg",
  pastry: "/icons/category/pastry.svg",
  pie: "/icons/category/pie_tart.svg",
  macaron: "/icons/category/macarons.svg",
  chocolate: "/icons/category/chocolate.svg",
};

export function categoryIcon(slug: string): string {
  return CATEGORY_ICONS[slug] ?? CATEGORY_OTHER_PHOTO;
}

/** Stand-ins for content the author never gave an image. */
export const PLACEHOLDER = {
  recipeCover: "/placeholders/recipe-cover.svg",
  courseCover: "/placeholders/course-cover.svg",
  postImage: "/placeholders/post-image.svg",
  avatar: "/placeholders/avatar.svg",
  certificate: "/placeholders/certificate.svg",
} as const;

export const BANNER = {
  home: "/banners/home-hero.svg",
} as const;

export const BRAND_MARK = "/brand/logo-mark.svg";

/**
 * Badge artwork for one catalogue slug.
 *
 * The catalogue is server-owned and can grow at any time, so an unknown
 * slug resolves to generic artwork instead of a broken image  a new
 * badge shipped by the backend looks plain, never broken. Unearned
 * badges share one padlock silhouette; that is a *display* decision made
 * from the earned flag the ledger already gave us, not a second source
 * of truth about whether it is earned.
 */
const BADGE_SLUGS = new Set([
  "course_completed",
  "first_course",
  "quiz_master",
  "recipe_author",
  "ten_courses",
]);

export function badgeArt(slug: string, earned: boolean): string {
  if (!earned) return "/achievements/locked.svg";
  return BADGE_SLUGS.has(slug)
    ? `/achievements/${slug}.svg`
    : "/achievements/default.svg";
}

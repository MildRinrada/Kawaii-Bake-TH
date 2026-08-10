# `public/` — static asset library

Everything here is served verbatim from the site root (`/icons/ui/search.svg`),
is cached hard by the CDN, and is **not** processed by the bundler. Anything
that needs to be imported, tree-shaken, or type-checked belongs in
`src/`, not here.

## Layout

| Folder | What lives here | How it is rendered |
|---|---|---|
| `banners/` | Wide decorative page artwork (hero backdrops). | `<img aria-hidden>` behind real HTML text — never text baked into the image. |
| `brand/` | The KawaiiBake mark. | `<img>` with a real `alt`. |
| `icons/ui/` | Monochrome 24×24 interface glyphs (search, close, trash, …). | `<Icon name="ui/search" />` — CSS mask, so it inherits `currentColor`. |
| `icons/admin/` | Monochrome 24×24 glyphs for the admin sidebar and admin tables. | `<Icon name="admin/users" />`. |
| `icons/modal/` | Full-colour 96×96 status art for dialogs (success, error, warning, info, confirm-delete, locked). | `<ArtIcon src={MODAL_ART.success} />`. |
| `icons/flavor/` | Full-colour 64×64 bakery motifs used as decoration and category art. | `<ArtIcon>`. |
| `achievements/` | Badge artwork, **one file per catalogue slug** (`course_completed.svg`, …) plus `locked.svg` and `default.svg`. | `badgeArt(slug, earned)` from `@/lib/assets`. |
| `placeholders/` | Stand-in artwork for content with no uploaded image. | `PLACEHOLDER.recipeCover` etc. from `@/lib/assets`. |

## Rules

1. **Monochrome vs colour is a hard split.** `icons/ui` and `icons/admin` are
   stroke-only and drawn in black; they are painted through
   `mask-image`, so their own colour never reaches the screen. Colour art
   (`modal/`, `flavor/`, `achievements/`, `placeholders/`, `banners/`) bakes in
   the token palette and must never be masked.
2. **Badge filenames are backend slugs.** `achievements/<slug>.svg` is looked up
   by the slug the catalogue returns (`GET /api/v1/achievements/`). A badge with
   no file falls back to `default.svg`, so adding a badge server-side can never
   break the page — it just looks generic until artwork lands.
3. **Placeholders must look like placeholders.** They say "ยังไม่มีภาพหน้าปก"
   on purpose. A pretty stock photo here would read as real user content.
4. **Nothing here is user data.** No uploaded media, ever — that lives in
   `MEDIA_ROOT` on the Django side and is served from the API origin.
5. `robots.txt` is a crawler *request*, not a control. The enforcement side is
   the threat-watch app on the backend (ADR 0025).

## Palette

Colours are copied from `src/styles/tokens.css` at authoring time. SVGs cannot
read CSS custom properties from the host page when loaded via `<img>`, so a
brand retune means re-exporting the colour art — this is the accepted cost of
keeping the icons as plain files rather than inline JSX.

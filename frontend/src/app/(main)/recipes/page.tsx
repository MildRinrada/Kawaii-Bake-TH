"use client";

/**
 * Recipe discovery: a smart baking library.
 *
 * The URL is the single source of truth for every dimension the real
 * API supports — search, categories (multi), difficulty (multi), a
 * time cap, an ingredient term (canonically folded server-side, Thai ↔
 * English), and ordering. Suggestions, the quick-category row, the
 * mobile filter sheet and the no-results recovery all drive the same
 * params. Saved-state hearts are seeded from the user's real favorites
 * list so every card can be saved without opening it.
 */

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";

import { api, type Paginated } from "@/lib/api/client";
import type {
  Category,
  FavoriteItem,
  RecipeListItem,
} from "@/lib/api/models";
import { useApiQuery } from "@/lib/hooks/use-api-query";
import { useAuth } from "@/lib/auth/auth-context";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { CategoryThumb, CategoryTile } from "@/components/content/category-tile";
import { Icon } from "@/components/ui/icon";
import { RecipeCard } from "@/components/content/recipe-card";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 12;

const DIFFICULTIES = [
  { value: "easy", label: "ง่าย" },
  { value: "medium", label: "ปานกลาง" },
  { value: "hard", label: "ยาก" },
  { value: "expert", label: "ขั้นสูง" },
];

const TIME_CAPS = [
  { value: "30", label: "ไม่เกิน 30 นาที" },
  { value: "60", label: "ไม่เกิน 1 ชม." },
  { value: "120", label: "ไม่เกิน 2 ชม." },
];

// Common pantry terms, matching how ingredients are written in recipes
// (the list filter is a normalized match on the stored Thai lines).
const PANTRY_CHIPS = ["ช็อกโกแลต", "เนย", "ไข่", "นม", "สตรอว์เบอร์รี", "ส้ม"];

const ORDERINGS: Array<{ value: string; label: string; needsSearch?: boolean }> = [
  { value: "newest", label: "มาใหม่" },
  { value: "relevance", label: "เกี่ยวข้องที่สุด", needsSearch: true },
  { value: "quickest", label: "เร็วที่สุด" },
  { value: "difficulty", label: "ง่ายไปยาก" },
  { value: "title", label: "ตามชื่อ" },
  { value: "oldest", label: "เก่าสุด" },
];

/* ------------------------------------------------------------------ */
/* Shared chip                                                         */
/* ------------------------------------------------------------------ */

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-full px-3.5 py-1.5 text-sm transition-colors",
        "focus-visible:outline-2 focus-visible:outline-focus",
        active
          ? "bg-accent font-medium text-fg-inverted shadow-raised"
          : "bg-surface text-fg-muted shadow-raised hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Search with grouped suggestions                                     */
/* ------------------------------------------------------------------ */

function SearchBox({
  initial,
  categories,
  onSearch,
  onIngredient,
  onCategory,
}: {
  initial: string;
  categories: Category[];
  onSearch: (term: string) => void;
  onIngredient: (term: string) => void;
  onCategory: (slug: string) => void;
}) {
  const router = useRouter();
  const [value, setValue] = useState(initial);
  const [open, setOpen] = useState(false);
  const [recipeHits, setRecipeHits] = useState<RecipeListItem[]>([]);

  // Sync when the URL changes underneath us (back button, clear-all).
  const [seen, setSeen] = useState(initial);
  if (seen !== initial) {
    setSeen(initial);
    setValue(initial);
  }

  const term = value.trim();

  // Debounced live suggestions from the real search endpoint.
  useEffect(() => {
    if (term.length < 2) return;
    const handle = setTimeout(() => {
      api
        .get<Paginated<RecipeListItem>>("/recipes/", {
          query: { search: term, page_size: 3 },
        })
        .then((data) => setRecipeHits(data.results))
        .catch(() => {});
    }, 300);
    return () => clearTimeout(handle);
  }, [term]);

  const categoryHits =
    term.length >= 1
      ? categories
          .filter((category) =>
            `${category.name} ${category.slug}`
              .toLowerCase()
              .includes(term.toLowerCase()),
          )
          .slice(0, 3)
      : [];
  const showPanel = open && term.length >= 2;

  function choose(action: () => void) {
    setOpen(false);
    action();
  }

  return (
    <div className="relative max-w-xl">
      <form
        role="search"
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          choose(() => onSearch(term));
        }}
      >
        <Input
          type="search"
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
          placeholder="ค้นหาสูตร หรือวัตถุดิบ เช่น ครัวซองต์, ช็อกโกแลต…"
          aria-label="ค้นหาสูตรขนม"
          aria-expanded={showPanel}
          className="rounded-full"
        />
        <Button type="submit" variant="secondary">
          ค้นหา
        </Button>
      </form>

      {showPanel ? (
        <div className="absolute inset-x-0 top-full z-40 mt-2 overflow-hidden rounded-surface border border-edge bg-surface shadow-overlay">
          {recipeHits.length > 0 ? (
            <div className="border-b border-edge p-2">
              <p className="px-2 pb-1 text-xs font-medium text-fg-subtle">สูตรขนม</p>
              {recipeHits.map((recipe) => (
                <button
                  key={recipe.slug}
                  type="button"
                  onClick={() =>
                    choose(() => router.push(`/recipes/${recipe.slug}`))
                  }
                  className="flex w-full items-center gap-2 rounded-control px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
                >
                  <Icon name="ui/sparkle" className="size-3.5 shrink-0" />
                  <span className="truncate">{recipe.title}</span>
                  <span className="ml-auto shrink-0 text-xs text-fg-subtle">
                    {recipe.total_minutes} นาที
                  </span>
                </button>
              ))}
            </div>
          ) : null}
          {categoryHits.length > 0 ? (
            <div className="border-b border-edge p-2">
              <p className="px-2 pb-1 text-xs font-medium text-fg-subtle">หมวด</p>
              {categoryHits.map((category) => (
                <button
                  key={category.slug}
                  type="button"
                  onClick={() => choose(() => onCategory(category.slug))}
                  className="flex w-full items-center gap-2 rounded-control px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
                >
                  <CategoryThumb slug={category.slug} />
                  {category.name}
                  <span className="ml-auto text-xs text-fg-subtle">
                    {category.recipe_count} สูตร
                  </span>
                </button>
              ))}
            </div>
          ) : null}
          <div className="p-2">
            <button
              type="button"
              onClick={() => choose(() => onSearch(term))}
              className="flex w-full items-center gap-2 rounded-control px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
            >
              🔍 ค้นหา “{term}” ในชื่อสูตร
            </button>
            <button
              type="button"
              onClick={() => choose(() => onIngredient(term))}
              className="flex w-full items-center gap-2 rounded-control px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus"
            >
              <Icon name="ui/salt" className="size-3.5" /> หาสูตรที่ใช้ “{term}” เป็นวัตถุดิบ
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Saveable card — heart seeded from the user's real favorites         */
/* ------------------------------------------------------------------ */

function SaveableRecipeCard({
  recipe,
  saved,
  canSave,
  onToggle,
}: {
  recipe: RecipeListItem;
  saved: boolean;
  canSave: boolean;
  onToggle: (slug: string, next: boolean) => void;
}) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);

  async function toggle() {
    setBusy(true);
    try {
      if (saved) {
        await api.delete(`/recipes/${recipe.slug}/favorite/`);
        onToggle(recipe.slug, false);
        toast("นำออกจากรายการโปรดแล้ว");
      } else {
        await api.post(`/recipes/${recipe.slug}/favorite/`);
        onToggle(recipe.slug, true);
        toast("บันทึกเข้ารายการโปรดแล้ว", "success");
      }
    } catch {
      toast("ทำรายการไม่สำเร็จ ลองใหม่อีกครั้ง", "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative">
      <RecipeCard recipe={recipe} />
      {canSave ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => void toggle()}
          aria-pressed={saved}
          aria-label={
            saved
              ? `นำ ${recipe.title} ออกจากรายการโปรด`
              : `บันทึก ${recipe.title} เข้ารายการโปรด`
          }
          className={cn(
            "absolute right-3 top-3 flex size-11 items-center justify-center rounded-full text-lg shadow-raised backdrop-blur transition-transform",
            "focus-visible:outline-2 focus-visible:outline-focus",
            saved
              ? "bg-accent text-fg-inverted"
              : "bg-surface/90 text-accent hover:scale-110",
            busy && "opacity-60",
          )}
        >
          <Icon name={saved ? "ui/heart-filled" : "ui/heart"} className="size-5" />
        </button>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

function RecipesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status } = useAuth();

  const search = searchParams.get("search") ?? "";
  const categoryParam = searchParams.get("category") ?? "";
  const difficultyParam = searchParams.get("difficulty") ?? "";
  const maxMinutes = searchParams.get("max_total_minutes") ?? "";
  const ingredient = searchParams.get("ingredient") ?? "";
  const ordering = searchParams.get("ordering") ?? "";
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);

  const selectedCategories = categoryParam ? categoryParam.split(",") : [];
  const selectedDifficulties = difficultyParam ? difficultyParam.split(",") : [];
  const [sheetOpen, setSheetOpen] = useState(false);

  function setParams(updates: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    if (!("page" in updates)) params.delete("page");
    const qs = params.toString();
    router.replace((qs ? `/recipes?${qs}` : "/recipes") as Route, {
      scroll: false,
    });
  }

  function toggleInList(current: string[], value: string, key: string, max = 5) {
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : current.length < max
        ? [...current, value]
        : current;
    setParams({ [key]: next.join(",") || null });
  }

  const categories = useApiQuery(
    (signal) => api.get<Category[]>("/recipe-categories/", { signal }),
    [],
  );

  const { data, loading, error, refetch } = useApiQuery(
    (signal) =>
      api.get<Paginated<RecipeListItem>>("/recipes/", {
        query: {
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          category: categoryParam || undefined,
          difficulty: difficultyParam || undefined,
          max_total_minutes: maxMinutes || undefined,
          ingredient: ingredient || undefined,
          ordering: ordering || undefined,
        },
        signal,
      }),
    [page, search, categoryParam, difficultyParam, maxMinutes, ingredient, ordering],
  );

  // Fallback suggestions for the no-results state.
  const fallback = useApiQuery(
    (signal) =>
      api.get<Paginated<RecipeListItem>>("/recipes/", {
        query: { page_size: 3 },
        signal,
      }),
    [],
  );

  // The saved-state map: seeded once from the user's real favorites.
  const favorites = useApiQuery(
    (signal) =>
      status === "authenticated"
        ? api.get<Paginated<FavoriteItem>>("/users/me/favorites/", {
            query: { type: "recipe", page_size: 100 },
            signal,
          })
        : Promise.resolve(null),
    [status],
  );
  const [savedSlugs, setSavedSlugs] = useState<Set<string>>(new Set());
  const [favoritesSeeded, setFavoritesSeeded] = useState(false);
  if (favorites.data && !favoritesSeeded) {
    setFavoritesSeeded(true);
    setSavedSlugs(
      new Set(
        favorites.data.results
          .map((item) => (item.recipe as { slug?: string } | null)?.slug)
          .filter((slug): slug is string => Boolean(slug)),
      ),
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1;
  const activeFilterCount =
    selectedCategories.length +
    selectedDifficulties.length +
    (maxMinutes ? 1 : 0) +
    (ingredient ? 1 : 0);
  const filtered = Boolean(search || activeFilterCount);
  const categoryName = (slug: string) =>
    categories.data?.find((category) => category.slug === slug)?.name ?? slug;

  const clearAll = () =>
    setParams({
      search: null,
      category: null,
      difficulty: null,
      max_total_minutes: null,
      ingredient: null,
      ordering: null,
    });

  const filterControls = (
    <>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="กรองตามความยาก">
        <span className="text-xs font-medium text-fg-subtle">ความยาก:</span>
        {DIFFICULTIES.map((item) => (
          <FilterChip
            key={item.value}
            active={selectedDifficulties.includes(item.value)}
            onClick={() =>
              toggleInList(selectedDifficulties, item.value, "difficulty")
            }
          >
            {item.label}
          </FilterChip>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="กรองตามเวลา">
        <span className="text-xs font-medium text-fg-subtle">เวลา:</span>
        {TIME_CAPS.map((item) => (
          <FilterChip
            key={item.value}
            active={maxMinutes === item.value}
            onClick={() =>
              setParams({
                max_total_minutes: maxMinutes === item.value ? null : item.value,
              })
            }
          >
            {item.label}
          </FilterChip>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="กรองตามวัตถุดิบ">
        <span className="text-xs font-medium text-fg-subtle">มีวัตถุดิบ:</span>
        {PANTRY_CHIPS.map((term) => (
          <FilterChip
            key={term}
            active={ingredient === term}
            onClick={() =>
              setParams({ ingredient: ingredient === term ? null : term })
            }
          >
            {term}
          </FilterChip>
        ))}
      </div>
    </>
  );

  return (
    <PageContainer>
      <PageHeader
        title="สูตรขนม"
        description={
          data
            ? `ค้นพบสูตรใหม่ที่น่าลอง ทั้งหมด ${data.count} สูตร ตั้งแต่เมนูสำหรับมือใหม่ไปจนถึง Pastry ขั้นสูง`
            : "ค้นพบสูตรถัดไปของคุณ ตั้งแต่เมนูสำหรับมือใหม่ไปจนถึง Pastry ขั้นสูง"
        }
        actions={
          // The primary recipe-authoring entry point. Community posting
          // deliberately has no CTA on this page.
          <Link href="/recipes/create">
            <Button>+ เพิ่มสูตรอาหาร</Button>
          </Link>
        }
      />

      <SearchBox
        initial={search}
        categories={categories.data ?? []}
        onSearch={(term) => setParams({ search: term || null, ordering: term ? "relevance" : null })}
        onIngredient={(term) => setParams({ ingredient: term || null, search: null })}
        onCategory={(slug) => toggleInList(selectedCategories, slug, "category")}
      />

      {/* Quick categories — compact square photo tiles, horizontal scroll */}
      {categories.data && categories.data.length > 0 ? (
        <div
          className="mt-4 flex snap-x gap-2.5 overflow-x-auto pb-2"
          role="group"
          aria-label="หมวดขนม"
        >
          {categories.data.map((category) => (
            <CategoryTile
              key={category.slug}
              compact
              slug={category.slug}
              name={category.name}
              count={category.recipe_count}
              active={selectedCategories.includes(category.slug)}
              onClick={() =>
                toggleInList(selectedCategories, category.slug, "category")
              }
            />
          ))}
        </div>
      ) : null}

      {/* Filters: inline on desktop, bottom sheet on mobile */}
      <div className="mt-3 hidden space-y-2.5 lg:block">{filterControls}</div>
      <div className="mt-3 lg:hidden">
        <Button
          variant="secondary"
          size="sm"
          aria-expanded={sheetOpen}
          onClick={() => setSheetOpen(true)}
        >
          ⚙️ ตัวกรอง{activeFilterCount ? ` (${activeFilterCount})` : ""}
        </Button>
      </div>

      {/* Active filter summary */}
      {filtered ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-control bg-surface-sunken/70 px-3 py-2 text-sm">
          <span className="text-xs font-medium text-fg-subtle">กำลังกรอง:</span>
          {search ? (
            <FilterChip active onClick={() => setParams({ search: null, ordering: null })}>
              <>“{search}” <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ) : null}
          {ingredient ? (
            <FilterChip active onClick={() => setParams({ ingredient: null })}>
              <><Icon name="ui/salt" className="size-3.5" /> {ingredient} <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ) : null}
          {selectedCategories.map((slug) => (
            <FilterChip
              key={slug}
              active
              onClick={() => toggleInList(selectedCategories, slug, "category")}
            >
              <>{categoryName(slug)} <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ))}
          {selectedDifficulties.map((value) => (
            <FilterChip
              key={value}
              active
              onClick={() => toggleInList(selectedDifficulties, value, "difficulty")}
            >
              <>{DIFFICULTIES.find((item) => item.value === value)?.label} <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ))}
          {maxMinutes ? (
            <FilterChip active onClick={() => setParams({ max_total_minutes: null })}>
              <>≤ {maxMinutes} นาที <Icon name="ui/close" className="size-3" /></>
            </FilterChip>
          ) : null}
          <button
            type="button"
            onClick={clearAll}
            className="ml-auto text-xs text-fg-subtle underline hover:text-fg focus-visible:outline-2 focus-visible:outline-focus"
          >
            ล้างทั้งหมด
          </button>
        </div>
      ) : null}

      {/* Results header: count + sort */}
      <div className="mb-5 mt-6 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-muted" aria-live="polite">
          {data ? (
            <>
              พบ <strong className="text-fg">{data.count}</strong> สูตร
            </>
          ) : (
            "กำลังค้นหา…"
          )}
        </p>
        <label className="flex items-center gap-2 text-sm text-fg-muted">
          เรียงตาม
          <select
            value={ordering || "newest"}
            onChange={(event) =>
              setParams({
                ordering: event.target.value === "newest" ? null : event.target.value,
              })
            }
            className="rounded-full border border-edge-strong/50 bg-surface px-3 py-1.5 text-sm text-fg focus-visible:outline-2 focus-visible:outline-focus"
          >
            {ORDERINGS.filter((item) => !item.needsSearch || search).map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <div aria-busy="true" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-72 w-full rounded-surface" />
          ))}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <div className="space-y-8">
          <EmptyState
            title={
              search
                ? `ไม่พบสูตรที่ตรงกับ “${search}” พอดีเป๊ะ`
                : "ไม่พบสูตรตามเงื่อนไขที่เลือก"
            }
            description="ลองลดตัวกรองลง เปลี่ยนคำค้น หรือเริ่มจากหมวดใกล้เคียง"
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="secondary" size="sm" onClick={clearAll}>
                  ล้างตัวกรองทั้งหมด
                </Button>
                {(categories.data ?? []).slice(0, 4).map((category) => (
                  <Button
                    key={category.slug}
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setParams({
                        search: null,
                        ingredient: null,
                        category: category.slug,
                      })
                    }
                  >
                    <CategoryThumb slug={category.slug} /> {category.name}
                  </Button>
                ))}
              </div>
            }
          />
          {fallback.data && fallback.data.results.length > 0 ? (
            <section>
              <h2 className="font-display mb-4 text-lg font-medium text-fg">
                หรือลองสูตรเหล่านี้ดูก่อน
              </h2>
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {fallback.data.results.map((recipe) => (
                  <RecipeCard key={recipe.slug} recipe={recipe} />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : (
        <>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {data.results.map((recipe) => (
              <SaveableRecipeCard
                key={recipe.slug}
                recipe={recipe}
                saved={savedSlugs.has(recipe.slug)}
                canSave={status === "authenticated"}
                onToggle={(slug, next) =>
                  setSavedSlugs((current) => {
                    const set = new Set(current);
                    if (next) set.add(slug);
                    else set.delete(slug);
                    return set;
                  })
                }
              />
            ))}
          </div>
          {totalPages > 1 ? (
            <nav
              aria-label="เปลี่ยนหน้า"
              className="mt-8 flex items-center justify-center gap-3"
            >
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => setParams({ page: String(page - 1) })}
              >
                ← ก่อนหน้า
              </Button>
              <span className="text-sm text-fg-muted">
                หน้า {page} / {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setParams({ page: String(page + 1) })}
              >
                ถัดไป →
              </Button>
            </nav>
          ) : null}
        </>
      )}

      {/* Mobile filter sheet */}
      {sheetOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="ปิดตัวกรอง"
            onClick={() => setSheetOpen(false)}
            className="absolute inset-0 bg-fg/30"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="ตัวกรองสูตร"
            className="absolute inset-x-0 bottom-0 max-h-[80dvh] overflow-y-auto rounded-t-surface bg-surface p-5 shadow-overlay"
          >
            <div className="mb-4 flex items-center justify-between">
              <p className="font-display font-medium text-fg">
                ตัวกรอง{activeFilterCount ? ` (${activeFilterCount})` : ""}
              </p>
              <button
                type="button"
                onClick={clearAll}
                className="text-sm text-fg-subtle underline hover:text-fg"
              >
                ล้างทั้งหมด
              </button>
            </div>
            <div className="space-y-4">{filterControls}</div>
            <Button className="mt-5 w-full" size="lg" onClick={() => setSheetOpen(false)}>
              ดูผลลัพธ์{data ? ` (${data.count} สูตร)` : ""}
            </Button>
          </div>
        </div>
      ) : null}

      {/* Anonymous nudge — save requires an account */}
      {status === "anonymous" && data && data.results.length > 0 ? (
        <p className="mt-8 text-center text-sm text-fg-muted">
          <Link href="/login" className="font-medium text-accent underline">
            เข้าสู่ระบบ
          </Link>{" "}
          เพื่อกดหัวใจบันทึกสูตรเก็บไว้อบทีหลังได้เลย
        </p>
      ) : null}
    </PageContainer>
  );
}

export default function RecipesPage() {
  return (
    <Suspense>
      <RecipesContent />
    </Suspense>
  );
}

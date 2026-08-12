"use client";

/**
 * The one paginated-list hook every admin table uses.
 *
 * Filters live in component state (an admin table is a working surface,
 * not a shareable URL), and changing any of them resets to page 1 
 * otherwise page 4 of a narrowed result set silently renders empty.
 */

import { useEffect, useState } from "react";

import { api, type Paginated } from "@/lib/api/client";
import { useApiQuery } from "@/lib/hooks/use-api-query";

export type QueryValue = string | number | boolean | null | undefined;

export function usePagedList<T>(
  path: string,
  query: Record<string, QueryValue>,
  pageSize = 20,
) {
  const [page, setPage] = useState(1);

  // Filters are compared by value: the caller rebuilds the object each
  // render, so identity would reset the page on every keystroke.
  const key = JSON.stringify(query);
  const [lastKey, setLastKey] = useState(key);
  if (key !== lastKey) {
    setLastKey(key);
    setPage(1);
  }

  const state = useApiQuery<Paginated<T>>(
    (signal) =>
      api.get<Paginated<T>>(path, {
        // The caller's query spreads last so a `page_size` it carries
        // wins over the hook default - that is how a rows-per-page
        // select works (and, being part of `key`, changing it resets
        // to page 1 like any other filter).
        query: { page, page_size: pageSize, ...query },
        signal,
      }),
    [path, key, page, pageSize],
  );

  return {
    ...state,
    rows: state.data?.results ?? [],
    count: state.data?.count ?? 0,
    page,
    setPage,
    pageSize: Number(query.page_size ?? pageSize),
  };
}

/** Debounce a search box so typing does not fire a request per keystroke. */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

"use client";

/**
 * Tiny client-side data hook: loading / error / data, with abort on
 * unmount. Enough for structural shells; if the app later needs caches,
 * mutations and revalidation, swap in TanStack Query behind the same
 * call sites  the fetcher already is the shared API client.
 */

import { useCallback, useEffect, useRef, useState } from "react";

interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

export function useApiQuery<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
) {
  const [state, setState] = useState<QueryState<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const [nonce, setNonce] = useState(0);

  // Latest fetcher without re-running the effect on identity changes 
  // the ref is written inside an effect, never during render.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    const controller = new AbortController();
    fetcherRef
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ data, loading: false, error: null });
        }
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) {
          setState({ data: null, loading: false, error });
        }
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const refetch = useCallback(() => {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    setNonce((value) => value + 1);
  }, []);

  return { ...state, refetch };
}

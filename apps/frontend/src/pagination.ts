import { useEffect, useMemo, useRef } from "react";

import { useRememberedState } from "./remembered";

export const PAGE_SIZE_OPTIONS = [10, 25, 50];

export interface PaginatedItems<T> {
  items: T[];
  page: number;
  pageCount: number;
  pageSize: number;
  totalItems: number;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
}

/**
 * Client-side pages over `items`. With `rememberKey`, the page and page size are kept for
 * the session, so returning to a screen keeps the operator's place.
 */
export function usePagination<T>(
  items: T[],
  pageSize: number,
  resetKey = "",
  rememberKey?: string,
): PaginatedItems<T> {
  const [requestedPage, setRequestedPage] = useRememberedState(
    rememberKey ? `${rememberKey}:page` : undefined,
    1,
  );
  const [chosenPageSize, setChosenPageSize] = useRememberedState(
    rememberKey ? `${rememberKey}:page-size` : undefined,
    pageSize,
  );
  const pageCount = Math.max(1, Math.ceil(items.length / chosenPageSize));
  const page = Math.min(requestedPage, pageCount);

  // Back to page 1 when the filters change, but not on the first render, which would
  // throw away a remembered page.
  const previousResetKey = useRef(resetKey);
  useEffect(() => {
    if (previousResetKey.current === resetKey) return;
    previousResetKey.current = resetKey;
    setRequestedPage(1);
  }, [resetKey, setRequestedPage]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * chosenPageSize;
    return items.slice(start, start + chosenPageSize);
  }, [items, page, chosenPageSize]);

  return {
    items: pageItems,
    page,
    pageCount,
    pageSize: chosenPageSize,
    totalItems: items.length,
    setPage: setRequestedPage,
    setPageSize: (size: number) => {
      setChosenPageSize(size);
      setRequestedPage(1);
    },
  };
}

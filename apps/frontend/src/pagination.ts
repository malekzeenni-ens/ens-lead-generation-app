import { useEffect, useMemo, useState } from "react";

export interface PaginatedItems<T> {
  items: T[];
  page: number;
  pageCount: number;
  pageSize: number;
  totalItems: number;
  setPage: (page: number) => void;
}

export function usePagination<T>(
  items: T[],
  pageSize: number,
  resetKey = "",
): PaginatedItems<T> {
  const [requestedPage, setRequestedPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const page = Math.min(requestedPage, pageCount);

  useEffect(() => {
    setRequestedPage(1);
  }, [resetKey]);

  useEffect(() => {
    setRequestedPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, pageSize]);

  return {
    items: pageItems,
    page,
    pageCount,
    pageSize,
    totalItems: items.length,
    setPage: setRequestedPage,
  };
}

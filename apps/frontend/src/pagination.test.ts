import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { usePagination } from "./pagination";

describe("usePagination", () => {
  it("slices the first page of items by page size", () => {
    const items = Array.from({ length: 25 }, (_, index) => index);
    const { result } = renderHook(() => usePagination(items, 8));

    expect(result.current.items).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
    expect(result.current.page).toBe(1);
    expect(result.current.pageCount).toBe(4);
    expect(result.current.totalItems).toBe(25);
  });

  it("returns at least one page even when there are no items", () => {
    const { result } = renderHook(() => usePagination<number>([], 8));

    expect(result.current.items).toEqual([]);
    expect(result.current.page).toBe(1);
    expect(result.current.pageCount).toBe(1);
  });

  it("navigates to a later page via setPage", () => {
    const items = Array.from({ length: 25 }, (_, index) => index);
    const { result } = renderHook(() => usePagination(items, 8));

    act(() => {
      result.current.setPage(3);
    });

    expect(result.current.page).toBe(3);
    expect(result.current.items).toEqual([16, 17, 18, 19, 20, 21, 22, 23]);
  });

  it("clamps the requested page to the last available page", () => {
    const items = Array.from({ length: 25 }, (_, index) => index);
    const { result } = renderHook(() => usePagination(items, 8));

    act(() => {
      result.current.setPage(99);
    });

    expect(result.current.page).toBe(4);
    expect(result.current.items).toEqual([24]);
  });

  it("clamps the current page down when the item list shrinks", () => {
    const { result, rerender } = renderHook(({ items }) => usePagination(items, 8), {
      initialProps: { items: Array.from({ length: 25 }, (_, index) => index) },
    });

    act(() => {
      result.current.setPage(4);
    });
    expect(result.current.page).toBe(4);

    rerender({ items: Array.from({ length: 5 }, (_, index) => index) });

    expect(result.current.page).toBe(1);
    expect(result.current.pageCount).toBe(1);
    expect(result.current.items).toEqual([0, 1, 2, 3, 4]);
  });

  it("resets to page 1 when the reset key changes", () => {
    const items = Array.from({ length: 25 }, (_, index) => index);
    const { result, rerender } = renderHook(
      ({ resetKey }) => usePagination(items, 8, resetKey),
      { initialProps: { resetKey: "first" } },
    );

    act(() => {
      result.current.setPage(3);
    });
    expect(result.current.page).toBe(3);

    rerender({ resetKey: "second" });

    expect(result.current.page).toBe(1);
  });
});

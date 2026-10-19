import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { usePagination } from "../pagination";
import { Collapsible, Drawer, MoreMenu, Pagination, StatusPill, Toolbar } from "./DesignSystem";

describe("Collapsible", () => {
  it("expands, collapses, shows a summary while closed and remembers its state", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <Collapsible rememberKey="test-notes" title="Notes" summary="3 notes">
        <p>Note body</p>
      </Collapsible>,
    );
    const toggle = screen.getByRole("button", { name: "Notes" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Note body")).toBeVisible();
    expect(screen.queryByText("3 notes")).not.toBeInTheDocument();

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Note body")).not.toBeVisible();
    expect(screen.getByText("3 notes")).toBeInTheDocument();

    unmount();
    render(
      <Collapsible rememberKey="test-notes" title="Notes" summary="3 notes">
        <p>Note body</p>
      </Collapsible>,
    );
    expect(screen.getByRole("button", { name: /Notes/ })).toHaveAttribute("aria-expanded", "false");
  });
});

describe("Drawer", () => {
  function Harness({ onClose }: { onClose?: () => void }) {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>Edit campaign</button>
        <Drawer
          open={open}
          title="Edit campaign"
          onClose={() => {
            onClose?.();
            setOpen(false);
          }}
          footer={<button type="button">Save</button>}
        >
          <input aria-label="Name" />
        </Drawer>
      </>
    );
  }

  it("moves focus inside, keeps it there, closes on Escape and returns focus", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByRole("button", { name: "Edit campaign" });
    await user.click(opener);

    const dialog = screen.getByRole("dialog", { name: "Edit campaign" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "Close Edit campaign" })).toHaveFocus();

    await user.tab();
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Save" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Close Edit campaign" })).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});

describe("Pagination", () => {
  it("offers rows per page and reports the change", async () => {
    const user = userEvent.setup();
    const onPageSizeChange = vi.fn();
    render(
      <Pagination
        page={1}
        pageCount={3}
        pageSize={10}
        totalItems={30}
        itemLabel="leads"
        onPageChange={vi.fn()}
        onPageSizeChange={onPageSizeChange}
      />,
    );
    await user.selectOptions(screen.getByRole("combobox", { name: "leads per page" }), "25");
    expect(onPageSizeChange).toHaveBeenCalledWith(25);
  });
});

describe("usePagination", () => {
  it("keeps a remembered page across remounts and resets only when filters change", () => {
    const items = Array.from({ length: 30 }, (_, index) => index);
    const first = renderHook(({ reset }) => usePagination(items, 10, reset, "test-list"), {
      initialProps: { reset: "a" },
    });
    act(() => first.result.current.setPage(3));
    expect(first.result.current.page).toBe(3);
    first.unmount();

    const second = renderHook(({ reset }) => usePagination(items, 10, reset, "test-list"), {
      initialProps: { reset: "a" },
    });
    expect(second.result.current.page).toBe(3);
    second.rerender({ reset: "b" });
    expect(second.result.current.page).toBe(1);

    act(() => second.result.current.setPageSize(25));
    expect(second.result.current.pageSize).toBe(25);
    expect(second.result.current.pageCount).toBe(2);
  });
});

describe("StatusPill and Toolbar", () => {
  it("renders a tone and lets filters be removed or cleared", async () => {
    const user = userEvent.setup();
    const removeStage = vi.fn();
    const clearAll = vi.fn();
    render(
      <>
        <StatusPill tone="warning">Needs review</StatusPill>
        <Toolbar
          chips={[{ label: "Stage: Qualified", onRemove: removeStage }]}
          onClearAll={clearAll}
          summary="Showing 1–10 of 42"
        >
          <input aria-label="Search" />
        </Toolbar>
      </>,
    );
    expect(screen.getByText("Needs review")).toHaveClass("status-pill--warning");
    await user.click(screen.getByRole("button", { name: "Remove filter Stage: Qualified" }));
    expect(removeStage).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Clear all" }));
    expect(clearAll).toHaveBeenCalled();
    expect(screen.getByText("Showing 1–10 of 42")).toBeInTheDocument();
  });
});

describe("MoreMenu", () => {
  it("opens, runs an action and closes, and closes on Escape", async () => {
    const user = userEvent.setup();
    const archive = vi.fn();
    const { container } = render(
      <MoreMenu label="More actions for Luton">
        <button type="button" onClick={archive}>Archive</button>
      </MoreMenu>,
    );
    const details = container.querySelector("details");
    await user.click(screen.getByLabelText("More actions for Luton"));
    expect(details).toHaveAttribute("open");
    await user.click(screen.getByRole("button", { name: "Archive" }));
    expect(archive).toHaveBeenCalled();
    expect(details).not.toHaveAttribute("open");

    await user.click(screen.getByLabelText("More actions for Luton"));
    expect(details).toHaveAttribute("open");
    await user.keyboard("{Escape}");
    expect(details).not.toHaveAttribute("open");
  });
});

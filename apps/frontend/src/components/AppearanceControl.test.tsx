import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applyTheme, readTheme, useAppearance } from "../appearance";
import { AppearanceControl } from "./AppearanceControl";
import { AppearanceProvider } from "./AppearanceProvider";

function SettingsProbe() {
  const { theme, density, setTheme, setDensity } = useAppearance();
  return (
    <>
      <output aria-label="Stored preference">{theme}</output>
      <output aria-label="Density preference">{density}</output>
      <button onClick={() => setTheme("system")}>Match Windows</button>
      <button onClick={() => setDensity("compact")}>Compact</button>
      <label>Unsaved note<input /></label>
    </>
  );
}

function Controls() {
  return <AppearanceProvider><AppearanceControl /><SettingsProbe /></AppearanceProvider>;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("shared EnS appearance", () => {
  it("restores legacy light/compact values and updates one live preference without losing form state", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("ens:appearance:theme", "light");
    window.localStorage.setItem("ens:appearance:density", "compact");
    applyTheme(readTheme());
    const first = render(<Controls />);
    expect(screen.getByRole("button", { name: "Bright theme" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Density preference")).toHaveTextContent("compact");
    const note = screen.getByLabelText("Unsaved note");
    await user.type(note, "Keep this draft");
    await user.click(screen.getByRole("button", { name: "Dark theme" }));
    expect(screen.getByLabelText("Stored preference")).toHaveTextContent("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem("ens:appearance:theme")).toBe("dark");
    expect(screen.getByLabelText("Unsaved note")).toBe(note);
    expect(note).toHaveValue("Keep this draft");
    first.unmount();
    render(<Controls />);
    expect(screen.getByRole("button", { name: "Dark theme" })).toHaveAttribute("aria-pressed", "true");
  });

  it("reflects Windows changes only while following system and keeps that preference stored as system", async () => {
    const user = userEvent.setup();
    let light = true;
    const listeners = new Set<() => void>();
    vi.stubGlobal("matchMedia", vi.fn(() => ({
      get matches() { return light; },
      addEventListener: (_event: string, callback: () => void) => listeners.add(callback),
      removeEventListener: (_event: string, callback: () => void) => listeners.delete(callback),
    })));
    const view = render(<Controls />);
    expect(screen.getByRole("button", { name: "Bright theme" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Stored preference")).toHaveTextContent("system");
    act(() => { light = false; listeners.forEach((callback) => callback()); });
    expect(screen.getByRole("button", { name: "Dark theme" })).toHaveAttribute("aria-pressed", "true");
    expect(window.localStorage.getItem("ens:appearance:theme")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Bright theme" }));
    act(() => { light = false; listeners.forEach((callback) => callback()); });
    expect(screen.getByRole("button", { name: "Bright theme" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Match Windows" }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(screen.getByRole("button", { name: "Dark theme" })).toHaveAttribute("aria-pressed", "true");
    view.unmount();
    expect(listeners.size).toBe(0);
  });

  it("keeps appearance usable when preference storage is unavailable", async () => {
    const user = userEvent.setup();
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Unavailable"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Unavailable"); });
    render(<Controls />);
    await user.click(screen.getByRole("button", { name: "Bright theme" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(screen.getByRole("button", { name: "Bright theme" })).toHaveAttribute("aria-pressed", "true");
  });
});

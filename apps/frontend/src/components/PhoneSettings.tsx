import { Laptop, Palette, Smartphone } from "lucide-react";
import { useState } from "react";

import { api } from "../api";
import { type DensityChoice, type ThemeChoice, useAppearance } from "../appearance";
import type { MobileSession } from "../types";
import { DangerConfirm, PageHeader } from "./DesignSystem";

/** Settings on a phone: this phone's own display choices and pairing; the rest is on the PC. */
export function PhoneSettings({ session }: { session: MobileSession }) {
  const { theme, setTheme, density, setDensity } = useAppearance();
  const [error, setError] = useState<string | null>(null);

  async function signOut(): Promise<void> {
    try {
      await api.signOutPhone();
      window.location.assign("/");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Signing out didn't work. Try again.");
    }
  }

  return (
    <>
      <PageHeader title="Settings" description="Display choices for this phone." />
      <div className="phone-settings">
        <section className="form-panel">
          <div className="subsection-heading">
            <div><h3>Appearance</h3><p>Applies straight away, on this phone only.</p></div>
            <Palette size={19} aria-hidden="true" />
          </div>
          <div className="form-grid">
          <fieldset className="choice-group">
            <legend>Theme</legend>
            {(
              [
                ["system", "Match this phone"],
                ["light", "Light"],
                ["dark", "Dark"],
              ] as [ThemeChoice, string][]
            ).map(([value, label]) => (
              <label key={value}>
                <input type="radio" name="phone-theme" checked={theme === value} onChange={() => setTheme(value)} />
                {label}
              </label>
            ))}
          </fieldset>
          <fieldset className="choice-group">
            <legend>Density</legend>
            {(
              [
                ["comfortable", "Comfortable"],
                ["compact", "Compact"],
              ] as [DensityChoice, string][]
            ).map(([value, label]) => (
              <label key={value}>
                <input type="radio" name="phone-density" checked={density === value} onChange={() => setDensity(value)} />
                {label}
              </label>
            ))}
          </fieldset>
          </div>
        </section>

        <section className="form-panel">
          <div className="subsection-heading">
            <div>
              <h3>This phone</h3>
              <p>Signed in as <strong>{session.device?.name ?? "this phone"}</strong>.</p>
            </div>
            <Smartphone size={19} aria-hidden="true" />
          </div>
          <div className="form-grid">
            <p className="supporting-copy">
              Signing out removes this phone from your PC. To use it again, pair it from Settings on the PC.
            </p>
            <DangerConfirm intensity="two-step" label="Sign out this phone" onConfirm={() => void signOut()} />
            {error ? <p className="form-error" role="alert">{error}</p> : null}
          </div>
        </section>

        <section className="form-panel">
          <div className="subsection-heading">
            <div>
              <h3>Manage on your PC</h3>
              <p>
                Connections, keys, backups, exports, campaign defaults, phone pairing, and changes to
                products and templates stay on your PC.
              </p>
            </div>
            <Laptop size={19} aria-hidden="true" />
          </div>
          <p className="supporting-copy">Your data stays on the PC. This phone shows it and keeps nothing.</p>
        </section>
      </div>
    </>
  );
}

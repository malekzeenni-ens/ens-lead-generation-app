import { Laptop, LockKeyhole, RefreshCw, Smartphone } from "lucide-react";
import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from "react";

import brandMarkUrl from "../../../desktop/brand-logo.png";
import { ApiError, api, onPhoneUnpaired, PHONE_NOT_PAIRED } from "../api";
import { browserLabel, codeFromLocation } from "../pairing";
import type { MobileSession } from "../types";

type GateState =
  | { kind: "checking" }
  | { kind: "unpaired" }
  | { kind: "unreachable"; message: string }
  | { kind: "ready"; session: MobileSession };

/**
 * On a phone, the workspace appears only once this phone is paired and the PC answers
 * (ADR-025). If the pairing goes away mid-session, it comes back to the pairing screen.
 */
export function PhoneGate({ children }: { children: (session: MobileSession) => ReactNode }) {
  const [state, setState] = useState<GateState>({ kind: "checking" });

  const check = useCallback(async () => {
    setState({ kind: "checking" });
    try {
      setState({ kind: "ready", session: await api.mobileSession() });
    } catch (caught) {
      if (caught instanceof ApiError && caught.details.code === PHONE_NOT_PAIRED) {
        setState({ kind: "unpaired" });
      } else {
        setState({
          kind: "unreachable",
          message: caught instanceof Error ? caught.message : "Your PC isn't reachable.",
        });
      }
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);
  useEffect(() => onPhoneUnpaired(() => setState({ kind: "unpaired" })), []);

  if (state.kind === "ready") return <>{children(state.session)}</>;
  return (
    <main className="phone-gate">
      <img className="phone-gate__logo" src={brandMarkUrl} alt="Etch ’N’ Shine" width="56" height="56" />
      {state.kind === "checking" ? (
        <p className="phone-gate__status" role="status">
          <RefreshCw className="spin" size={18} aria-hidden="true" /> Connecting to your PC…
        </p>
      ) : state.kind === "unpaired" ? (
        <PairingForm
          onPaired={(session) => {
            window.history.replaceState(null, "", "/");
            setState({ kind: "ready", session });
          }}
        />
      ) : (
        <PcUnreachable message={state.message} onRetry={() => void check()} />
      )}
    </main>
  );
}

function PcUnreachable({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className="phone-gate__card" aria-labelledby="pc-unreachable-heading">
      <span className="phone-gate__icon" aria-hidden="true"><Laptop size={26} /></span>
      <h1 id="pc-unreachable-heading">Your PC isn't reachable</h1>
      <p>{message}</p>
      <ul className="phone-gate__checks">
        <li>The PC is switched on and not asleep.</li>
        <li>Etch N Shine is open on the PC, with phone access on.</li>
        <li>Tailscale is signed in on both the PC and this phone.</li>
      </ul>
      <button type="button" className="primary-action" onClick={onRetry}>
        <RefreshCw size={17} aria-hidden="true" /> Try again
      </button>
    </section>
  );
}

function PairingForm({ onPaired }: { onPaired: (session: MobileSession) => void }) {
  const [code, setCode] = useState(() => codeFromLocation(window.location));
  const [name, setName] = useState(() => browserLabel(navigator.userAgent).replace(/^.* on /, "My "));
  const [error, setError] = useState<string | null>(null);
  const [pairing, setPairing] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPairing(true);
    setError(null);
    try {
      onPaired(await api.pairPhone(code, name, browserLabel(navigator.userAgent)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pairing didn't work. Try again.");
    } finally {
      setPairing(false);
    }
  }

  return (
    <section className="phone-gate__card" aria-labelledby="pair-heading">
      <span className="phone-gate__icon" aria-hidden="true"><LockKeyhole size={26} /></span>
      <h1 id="pair-heading">Pair this phone</h1>
      <p>
        On your PC, open <strong>Settings → Phone access</strong> and choose <strong>Pair a phone</strong>.
        Scan the code, or type it here. It works once and expires after 5 minutes.
      </p>
      <form className="phone-gate__form" onSubmit={(event) => void submit(event)}>
        <label>
          Pairing code
          <input
            id="pairing-code"
            className="phone-gate__code"
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            autoComplete="one-time-code"
            autoCapitalize="characters"
            spellCheck={false}
            inputMode="text"
            required
            minLength={8}
            maxLength={20}
            placeholder="ABCD-2345"
          />
        </label>
        <label>
          Name this phone
          <input
            id="pairing-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            maxLength={60}
          />
        </label>
        {error ? <p className="phone-gate__error" role="alert">{error}</p> : null}
        <button type="submit" className="primary-action" disabled={pairing}>
          <Smartphone size={17} aria-hidden="true" /> {pairing ? "Pairing…" : "Pair"}
        </button>
      </form>
      <p className="phone-gate__fine">You can remove this phone at any time in Settings on your PC.</p>
    </section>
  );
}

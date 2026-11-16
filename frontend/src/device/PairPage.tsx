import { LangSwitch, useT } from "../i18n";
import { type FormEvent, useState } from "react";
import { useDevice } from "./DeviceContext";

/** Shown once on a new phone: type the code the super user generated, then never log in again. */
export function PairPage({ initialCode = "" }: { initialCode?: string }) {
  const { pair } = useDevice();
  const { t } = useT();
  const [code, setCode] = useState(initialCode.toUpperCase());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await pair(code);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("pair.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page pair">
      <div className="brandbar">
        <img src="/logo.png" alt="" />
        <div>
          <strong>BHH Access</strong>
          <span className="muted">{t("app.subtitle")}</span>
        </div>
        <LangSwitch />
      </div>
      <h1>{t("pair.title")}</h1>
      <p className="muted">{t("pair.intro")}</p>
      <form onSubmit={submit} className="stack">
        <label>
          {t("pair.code")}
          <input
            className="code-input"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            autoComplete="off"
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            inputMode="text"
            maxLength={12}
            required
          />
        </label>
        {error && <p role="alert" className="error">{error}</p>}
        <button className="primary" disabled={busy || code.trim().length < 4}>
          {busy ? t("pair.busy") : t("pair.submit")}
        </button>
      </form>
    </main>
  );
}

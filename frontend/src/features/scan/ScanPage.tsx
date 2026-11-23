import { LangSwitch, useT } from "../../i18n";
import { useEffect, useState } from "react";
import type { Scanner } from "../../api/endpoints";
import type { Checkpoint, RecentScan } from "../../api/types";
import { ManualEntry } from "./ManualEntry";
import { QrScanner } from "./QrScanner";
import { ResultOverlay } from "./ResultOverlay";
import { ScanHistory } from "./ScanHistory";
import { useScanner } from "./useScanner";
import { speak } from "../../lib/voice";

interface Props {
  api: Scanner;
  checkpoint: Checkpoint;
  /** The opposite direction of the same zone, when it exists (single door). */
  otherSide?: Checkpoint | null;
  onSwitchSide?: (checkpoint: Checkpoint) => void;
  onChangeCheckpoint: () => void;
  /** Say the result aloud (set per phone in the back-office). */
  voice?: boolean;
  /** The phone's last scans; the « Historique » button shows only when given. */
  history?: () => Promise<RecentScan[]>;
}

function useOnline(): boolean {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

export function ScanPage({ api, checkpoint, otherSide, onSwitchSide, onChangeCheckpoint, voice = false, history }: Props) {
  const { result, error, pending, scanToken, scanMatricule, dismiss } = useScanner(api, checkpoint.id, voice);
  const [controlStarted, setControlStarted] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const online = useOnline();
  const { lang, t } = useT();
  const scanning = online && !pending && !result && !error && !historyOpen; // camera paused while reading

  const startControl = () => {
    if (voice) speak(t("scan.controlStarted"), lang);
    setControlStarted(true);
  };

  if (!controlStarted) {
    return (
      <main className="scan scan-start">
        <button className="primary" type="button" onClick={startControl}>
          {t("scan.startControl")}
        </button>
      </main>
    );
  }

  return (
    <main className="scan">
      <header className="bar">
        <div>
          <strong>{checkpoint.name}</strong>
          <span className={`dir ${checkpoint.direction === "ENTREE" ? "in" : "out"}`}>
            {checkpoint.direction === "ENTREE" ? t("dir.in") : t("dir.out")}
          </span>
          <small>
            {checkpoint.unit_name} · {checkpoint.zone_name}
            {checkpoint.agent_name ? ` · ${checkpoint.agent_name}` : ""}
          </small>
        </div>
        <div className="bar-actions">
          <LangSwitch />
          {history && <button className="link" onClick={() => setHistoryOpen(true)}>{t("history.button")}</button>}
          <button className="link" onClick={onChangeCheckpoint}>{t("scan.change")}</button>
        </div>
      </header>
      {otherSide && onSwitchSide && (
        <div className="side-switch" role="group" aria-label={t("scan.side")}>
          {(checkpoint.direction === "ENTREE" ? [checkpoint, otherSide] : [otherSide, checkpoint])
            .map((side) => (
              <button
                key={side.id}
                aria-pressed={side.id === checkpoint.id}
                className={`${side.direction === "ENTREE" ? "in" : "out"}${side.id === checkpoint.id ? " on" : ""}`}
                disabled={pending}
                onClick={() => side.id !== checkpoint.id && onSwitchSide(side)}
              >
                {side.direction === "ENTREE" ? t("dir.in") : t("dir.out")}
              </button>
            ))}
        </div>
      )}

      {!online && <p role="alert" className="banner">{t("scan.offline")}</p>}

      {online && <QrScanner active={scanning} onDetect={scanToken} />}
      {pending && <p className="center muted">{t("scan.checking")}</p>}
      {error && (
        <div role="alert" className="error center">
          <p>{error}</p>
          <button onClick={dismiss}>{t("scan.retry")}</button>
        </div>
      )}
      <ManualEntry disabled={!online || pending} onSubmit={scanMatricule} />

      {result && <ResultOverlay result={result} onDismiss={dismiss} />}
      {historyOpen && history && <ScanHistory load={history} onClose={() => setHistoryOpen(false)} />}
    </main>
  );
}

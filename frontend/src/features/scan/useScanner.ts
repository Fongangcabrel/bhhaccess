import { t } from "../../i18n";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Scanner } from "../../api/endpoints";
import type { ScanResult } from "../../api/types";
import { giveFeedback } from "../../lib/feedback";
import { getLang } from "../../lib/lang";
import { scanAnnouncement, speak } from "../../lib/voice";
import { ScanGuard } from "../../lib/scanGuard";
import { describeVerdict } from "../../lib/verdicts";

// The next person should not wait: a green / blue verdict clears faster than a refusal.
const AUTO_DISMISS_MS = { ok: 2500, exit: 2500, deny: 4000 } as const;

/** Orchestrates one scan: debounce -> API call -> verdict -> feedback -> auto-resume. */
export function useScanner(api: Scanner, checkpointId: number, voice = false) {
  const guard = useRef(new ScanGuard());
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const timer = useRef<number>();

  const dismiss = useCallback(() => {
    window.clearTimeout(timer.current);
    setResult(null);
    setError(null);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const run = useCallback(
    async (call: () => Promise<ScanResult>) => {
      setPending(true);
      setError(null);
      try {
        const outcome = await call();
        setResult(outcome);
        const tone = describeVerdict(outcome.verdict).tone;
        giveFeedback(tone);
        if (voice) {
          const lang = getLang();
          speak(scanAnnouncement(outcome, lang), lang);
        }
        timer.current = window.setTimeout(dismiss, AUTO_DISMISS_MS[tone]);
      } catch (e) {
        setError(e instanceof Error ? e.message : t("scan.unknownError"));
        giveFeedback("deny");
      } finally {
        guard.current.release();
        setPending(false);
      }
    },
    [dismiss, voice],
  );

  const scanToken = useCallback(
    (token: string) => {
      if (guard.current.accept(token)) void run(() => api.scanQr(checkpointId, token));
    },
    [api, checkpointId, run],
  );

  const scanMatricule = useCallback(
    (matricule: string) => {
      if (guard.current.accept(`manual:${matricule}`)) void run(() => api.scanManual(checkpointId, matricule));
    },
    [api, checkpointId, run],
  );

  return { result, error, pending, scanToken, scanMatricule, dismiss };
}

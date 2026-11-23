import { useT } from "../../i18n";
import { useEffect, useState } from "react";
import type { RecentScan } from "../../api/types";
import { formatTime } from "../../lib/format";
import { describeVerdict } from "../../lib/verdicts";

interface Props {
  load: () => Promise<RecentScan[]>;
  onClose: () => void;
}

/** The phone's last scans (FR-68): time, person, result. Read only; loaded each time it opens. */
export function ScanHistory({ load, onClose }: Props) {
  const { t, lang } = useT();
  const [lines, setLines] = useState<RecentScan[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load().then(setLines).catch((e: Error) => setError(e.message));
  }, [load]);

  return (
    <section className="history" role="dialog" aria-label={t("history.title")}>
      <header className="bar">
        <div>
          <strong>{t("history.title")}</strong>
          <small>{t("history.window")}</small>
        </div>
        <button onClick={onClose}>{t("history.close")}</button>
      </header>
      <div className="history-body">
        {error && <p role="alert" className="error">{error}</p>}
        {!lines && !error && <p className="muted">{t("history.loading")}</p>}
        {lines?.length === 0 && <p className="muted">{t("history.empty")}</p>}
        {!!lines?.length && (
          <ol className="history-list">
            {lines.map((line) => {
              const view = describeVerdict(line.verdict, lang);
              return (
                <li key={line.id}>
                  <time dateTime={line.occurred_at}>{formatTime(line.occurred_at)}</time>
                  <span className="who">
                    {line.employee_name ?? t("history.unknown")}
                    <small>
                      {[line.employee_matricule, line.checkpoint_name, line.method === "MANUEL" ? t("history.manual") : null]
                        .filter(Boolean).join(" · ")}
                    </small>
                  </span>
                  <span className={`hv ${view.tone}`}>{view.short}</span>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
}

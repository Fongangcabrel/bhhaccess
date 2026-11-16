import { useT } from "../../i18n";
import { useState } from "react";
import type { ScanResult } from "../../api/types";
import { Silhouette } from "../../components/Silhouette";
import { formatTime } from "../../lib/format";
import { describeFlag, describeVerdict } from "../../lib/verdicts";

/** Soft-mode inconsistencies: written in the journal and reports, shown to the agent only through
 * the zone option (``warning``), never as a raw flag (SRS FR-82). */
const JOURNAL_ONLY = new Set(["DOUBLE_ENTREE", "SORTIE_SANS_ENTREE"]);

interface Props {
  result: ScanResult;
  onDismiss: () => void;
}

/** Full-screen verdict: colour first, then name, then the reason. */
export function ResultOverlay({ result, onDismiss }: Props) {
  const { t, lang } = useT();
  const view = describeVerdict(result.verdict, lang);
  const employee = result.employee;
  const flags = result.flags.filter((flag) => !JOURNAL_ONLY.has(flag));
  return (
    <button className={`overlay ${view.tone}`} onClick={onDismiss} aria-live="assertive">
      {result.warning === "DOUBLE_ENTREE" && (
        <span className="warning-band" role="alert">{t("result.doubleEntry")}</span>
      )}
      <strong className="verdict">{view.title}</strong>
      {employee && <Portrait url={employee.photo_url ?? null} name={`${employee.first_name} ${employee.last_name}`} />}
      {employee && (
        <div className="who">
          <span className="name">
            {employee.first_name} {employee.last_name}
          </span>
          <span>{employee.matricule}</span>
          {(employee.job_title || employee.department_name) && (
            <span className="muted-on">{[employee.job_title, employee.department_name].filter(Boolean).join(" · ")}</span>
          )}
        </div>
      )}
      {result.detail ? <p className="hint detail">{result.detail}</p> : view.hint && <p className="hint">{view.hint}</p>}
      {result.last_entry_at && (
        <p className="last-entry">
          {t("result.lastEntry")} <strong>{formatTime(result.last_entry_at)}</strong>
          {result.last_entry_checkpoint && <> · {result.last_entry_checkpoint}</>}
        </p>
      )}
      {flags.length > 0 && (
        <ul className="flags">
          {flags.map((flag) => (
            <li key={flag}>⚠ {describeFlag(flag, lang)}</li>
          ))}
        </ul>
      )}
      <span className="tap">{t("result.tap")}</span>
    </button>
  );
}

/** The photo the agent compares with the face (FR-63). Missing or broken: "Photo absente". */
function Portrait({ url, name }: { url: string | null; name: string }) {
  const [broken, setBroken] = useState(false);
  const { t } = useT();
  if (!url || broken) {
    return (
      <div className="portrait absent" role="img" aria-label={t("result.noPhoto")}>
        <Silhouette />
        <span>{t("result.noPhotoHint")}</span>
      </div>
    );
  }
  return <img className="portrait" src={url} alt={t("result.photoOf", { name })} onError={() => setBroken(true)} />;
}

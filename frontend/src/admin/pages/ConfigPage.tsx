import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import type { SystemSetting } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { ErrorNote, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

/** Texts of the settings (the server keeps them in French for the audit). */
const LABEL: Record<string, string> = {
  "session.access_minutes": tx("Durée d'un jeton d'accès"),
  "session.refresh_hours": tx("Durée maximale d'une session (renouvelée sans reconnexion)"),
  "alerts.default_seconds_between_units": tx("Temps de trajet par défaut entre deux unités"),
  "alerts.burst_count": tx("Rafale : nombre de scans d'un badge"),
  "alerts.burst_seconds": tx("Rafale : en moins de"),
  "alerts.refusal_count": tx("Refus répétés : nombre de refus"),
  "alerts.refusal_minutes": tx("Refus répétés : en moins de"),
};
const GROUP: Record<string, string> = { Sessions: tx("Sessions"), Alertes: tx("Alertes") };

/** Paramétrage ▸ Configuration (system.config): session durations and alert thresholds, applied at once. */
export function ConfigPage() {
  const { admin } = useAuth();
  const settings = useAsync(() => admin.settings(), []);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);

  const rows = settings.data ?? [];
  const shown = (s: SystemSetting) => draft[s.key] ?? String(s.value);
  const changes = Object.fromEntries(rows
    .filter((s) => draft[s.key] !== undefined && draft[s.key] !== String(s.value))
    .map((s) => [s.key, draft[s.key] === "" ? null : Number(draft[s.key])]));
  const groups = [...new Set(rows.map((s) => s.group))];

  const save = (values: Record<string, number | null>) => void act(async () => {
    await admin.updateSettings(values);
    setDraft({});
    setSaved(true);
    await settings.reload();
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save(changes);
  };

  return (
    <>
      <PageHeader title={tx("Configuration")} />
      <p className="muted">{tx("Les changements s'appliquent tout de suite et sont inscrits dans l'audit. Une session déjà ouverte garde sa durée.")}</p>
      <ErrorNote message={error ?? settings.error} />
      <form onSubmit={submit} onChange={() => setSaved(false)}>
        {groups.map((group) => (
          <section key={group} className="panel">
            <h2 className="panel-title flat">{GROUP[group] ?? group}</h2>
            <div className="settings-grid">
              {rows.filter((s) => s.group === group).map((s) => (
                <label key={s.key} className="setting">
                  <span>{LABEL[s.key] ?? s.label}</span>
                  <span className="setting-input">
                    <input type="number" min={s.minimum} max={s.maximum} step={1} required
                      value={shown(s)} onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })} />
                    <span className="muted">{s.unit}</span>
                  </span>
                  <small className="muted">
                    {tx("Valeur d'installation : {0} {1}", [s.default, s.unit])}
                    {s.customised && (
                      <> · <button type="button" className="link" onClick={() => save({ [s.key]: null })}>{tx("Rétablir")}</button></>
                    )}
                  </small>
                </label>
              ))}
            </div>
          </section>
        ))}
        {rows.length > 0 && (
          <div className="form-actions">
            <button className="primary" disabled={Object.keys(changes).length === 0}>{tx("Enregistrer")}</button>
            {saved && <span className="muted" role="status">{tx("Configuration enregistrée.")}</span>}
          </div>
        )}
      </form>
    </>
  );
}

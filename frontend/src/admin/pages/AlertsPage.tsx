import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import type { AlertRow, AlertStatus, AlertType, RevocationReason } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { safeStorage } from "../../lib/storage";
import { ALERT_VOICE_KEY, alertVoiceEnabled } from "../AdminLayout";
import { formatDateTime } from "../../lib/format";
import { Empty, ErrorNote, Field, Modal, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

const ALERT_LABEL: Record<AlertType, string> = {
  SIMULTANEE: tx("Utilisation simultanée"),
  BADGE_REVOQUE: tx("Badge révoqué présenté"),
  EMPLOYE_ARCHIVE: tx("QR d'un employé archivé"),
  HORS_HORAIRE: tx("Hors horaires"),
  RAFALE: tx("Rafale de scans"),
  REFUS_REPETES: tx("Refus répétés"),
};
const SERIOUS: AlertType[] = ["SIMULTANEE", "BADGE_REVOQUE", "EMPLOYE_ARCHIVE"];
/** The badge no longer opens anything: nothing to revoke, only to acknowledge. */
const ALREADY_DEAD: AlertType[] = ["BADGE_REVOQUE", "EMPLOYE_ARCHIVE"];
const TABS: { key: AlertStatus | "ALL"; label: string }[] = [
  { key: "NOUVELLE", label: tx("Nouvelles") },
  { key: "PRISE_EN_COMPTE", label: tx("Prises en compte") },
  { key: "ALL", label: tx("Toutes") },
];
const REASONS: [RevocationReason, string][] = [["PERTE", tx("Perte")], ["VOL", tx("Vol")], ["DEPART", tx("Départ")], ["AUTRE", tx("Autre")]];
const PAGE = 100;

/** Suspicious badge use (SRS FR-90 to FR-93): handled here, with the badge revocation at hand. */
export function AlertsPage() {
  const { admin, can } = useAuth();
  const [tab, setTab] = useState<AlertStatus | "ALL">("NOUVELLE");
  const [type, setType] = useState<AlertType | "">("");
  const [handling, setHandling] = useState<{ alert: AlertRow; revoke: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [voice, setVoice] = useState(alertVoiceEnabled);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkBusy, setBulkBusy] = useState(false);
  const list = useAsync(() => admin.alerts(tab === "ALL" ? undefined : tab, type || undefined, PAGE), [tab, type]);
  const reload = () => void list.reload();
  const selectable = (list.data ?? []).filter((alert) => alert.status === "NOUVELLE");
  const allSelected = selectable.length > 0 && selectable.every((alert) => selectedIds.includes(alert.id));

  const acknowledgeSelected = async () => {
    const chosen = selectable.filter((alert) => selectedIds.includes(alert.id));
    if (!chosen.length || !window.confirm(tx("Prendre en compte les {0} alertes sélectionnées ?", [chosen.length]))) return;
    setBulkBusy(true);
    setError(null);
    const failed: { id: number; message: string }[] = [];
    let succeeded = 0;
    for (const alert of chosen) {
      try {
        await admin.ackAlert(alert.id);
        succeeded += 1;
      } catch (e) {
        failed.push({ id: alert.id, message: e instanceof Error ? e.message : tx("Erreur inconnue") });
      }
    }
    setSelectedIds(failed.map((item) => item.id));
    if (failed.length) {
      setError(tx("Prise en compte partielle : {0} réussie(s), {1} échec(s). {2}",
        [succeeded, failed.length, failed.map((item) => `#${item.id} : ${item.message}`).join(" · ")]));
    }
    await list.reload();
    setBulkBusy(false);
  };

  return (
    <>
      <PageHeader title={tx("Alertes")} />
      <p className="muted intro">{tx("Usages suspects détectés au scan : badge présenté à deux postes trop vite, badge révoqué ou d'un employé archivé, tentatives hors horaires, rafales, refus répétés. Une alerte ne bloque rien : elle se prend en compte, ou mène à la révocation du badge.")}
      </p>
      <div className="alerts-bar">
        <div className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} className={tab === t.key ? "active" : ""}
              onClick={() => { setSelectedIds([]); setTab(t.key); }}>{t.label}</button>
          ))}
        </div>
        <label className="inline-label check">
          <input type="checkbox" aria-label={tx("Sélectionner toutes les alertes nouvelles affichées")}
            checked={allSelected} disabled={selectable.length === 0 || bulkBusy}
            onChange={(event) => setSelectedIds(event.target.checked ? selectable.map((alert) => alert.id) : [])} />
          {tx("Sélectionner toutes les alertes nouvelles affichées")} ({selectable.length})
        </label>
        <label className="inline-label check">
          <input type="checkbox" checked={voice} onChange={(e) => {
            safeStorage.set(ALERT_VOICE_KEY, e.target.checked ? "on" : "off");
            setVoice(e.target.checked);
          }} />{" "}{tx("Annoncer les nouvelles alertes à voix haute")}
        </label>
        <label className="inline-label">{tx("Type")}
          <select value={type} onChange={(e) => { setSelectedIds([]); setType(e.target.value as AlertType | ""); }}>
            <option value="">{tx("Tous")}</option>
            {(Object.keys(ALERT_LABEL) as AlertType[]).map((k) => <option key={k} value={k}>{ALERT_LABEL[k]}</option>)}
          </select>
        </label>
        {selectedIds.length > 0 && (
          <button className="primary" type="button" disabled={bulkBusy} onClick={() => void acknowledgeSelected()}>
            {bulkBusy ? tx("Traitement…") : tx("Prendre en compte la sélection ({0})", [selectedIds.length])}
          </button>
        )}
      </div>
      <ErrorNote message={error ?? list.error} />
      {list.data?.length === 0 && (
        <Empty>{tab === "NOUVELLE" ? tx("Aucune nouvelle alerte. Tout est calme.") : tx("Aucune alerte.")}</Empty>
      )}
      {!!list.data?.length && (
        <section className="panel flush">
          <table className="cards alerts">
            <thead><tr>
              <th />
              <th>{tx("Date et heure")}</th><th>{tx("Type")}</th><th>{tx("Personne")}</th>
              <th>{tx("Poste")}</th><th>{tx("Détail")}</th><th />
            </tr></thead>
            <tbody>
              {list.data.map((a) => (
                <tr key={a.id} className={a.status === "NOUVELLE" ? "new" : "done"}>
                  <td data-label={tx("Sélection")}><input type="checkbox" aria-label={tx("Sélectionner l'alerte {0}", [a.id])}
                    checked={selectedIds.includes(a.id)} disabled={a.status !== "NOUVELLE" || bulkBusy}
                    onChange={(event) => setSelectedIds((current) => event.target.checked
                      ? [...current, a.id]
                      : current.filter((id) => id !== a.id))} /></td>
                  <td>{formatDateTime(a.created_at)}</td>
                  <td><span className={`alert-type${SERIOUS.includes(a.type) ? " serious" : ""}`}>{ALERT_LABEL[a.type]}</span></td>
                  <td>
                    {a.employee_id ? (
                      <Link to={`/admin/employes/${a.employee_id}`}><strong>{a.employee_name}</strong></Link>
                    ) : <span className="muted">–</span>}
                    {a.employee_matricule && <><br /><span className="muted">{a.employee_matricule}</span></>}
                  </td>
                  <td>{a.checkpoint_name ?? "–"}{a.zone_name && <><br /><span className="muted">{a.zone_name}</span></>}</td>
                  <td>
                    {a.message}
                    {a.status === "PRISE_EN_COMPTE" && (
                      <span className="muted block">{tx("Prise en compte")}{" "}{a.handled_at ? `le ${formatDateTime(a.handled_at)}` : ""}{a.note ? ` · ${a.note}` : ""}</span>
                    )}
                  </td>
                  <td className="right">
                    {a.status === "NOUVELLE" && (
                      <div className="inline end">
                        <button className="small" onClick={() => setHandling({ alert: a, revoke: false })}>{tx("Prendre en compte")}</button>
                        {a.badge_id && can("badges.revoke") && !ALREADY_DEAD.includes(a.type) && (
                          <button className="small danger" onClick={() => setHandling({ alert: a, revoke: true })}>{tx("Révoquer le badge")}</button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {handling && (
        <HandleDialog {...handling} onClose={() => setHandling(null)}
          onDone={() => { setHandling(null); setSelectedIds([]); reload(); }} />
      )}
    </>
  );
}

function HandleDialog({ alert, revoke, onClose, onDone }: {
  alert: AlertRow; revoke: boolean; onClose: () => void; onDone: () => void;
}) {
  const { admin } = useAuth();
  const [note, setNote] = useState("");
  const [reason, setReason] = useState<RevocationReason>("VOL");
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const needsNote = revoke && reason === "AUTRE";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => (revoke ? admin.revokeFromAlert(alert.id, reason, note.trim()) : admin.ackAlert(alert.id, note.trim())), onDone);
  };
  return (
    <Modal title={revoke ? tx("Révoquer le badge") : tx("Prendre en compte l'alerte")} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <p><strong>{ALERT_LABEL[alert.type]}</strong>{alert.employee_name && <> · {alert.employee_name}</>}<br />
          <span className="muted">{alert.message}</span></p>
        {revoke && (
          <>
            <p>{tx("Le QR ne donnera plus accès dès maintenant ; l'alerte sera marquée comme prise en compte.")}</p>
            <fieldset className="reasons">
              <legend>{tx("Motif")}</legend>
              {REASONS.map(([value, label]) => (
                <label key={value} className="reason">
                  <input type="radio" name="reason" checked={reason === value} onChange={() => setReason(value)} />{label}
                </label>
              ))}
            </fieldset>
          </>
        )}
        <Field label={needsNote ? tx("Précision (obligatoire)") : tx("Note (facultatif)")}>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} required={needsNote}
            placeholder={revoke ? tx("Ex. badge copié, retrouvé chez un tiers…") : tx("Ex. vérifié avec le chef de poste")} />
        </Field>
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className={revoke ? "danger" : "primary"} disabled={needsNote && !note.trim()}>
            {revoke ? tx("Révoquer le badge") : tx("Prendre en compte")}
          </button>
        </footer>
      </form>
    </Modal>
  );
}


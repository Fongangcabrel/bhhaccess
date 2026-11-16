import { useState } from "react";
import type { PhotoPurgeRequest, PurgeRequest } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { tx } from "../i18n";
import { endOfDayIso, startOfDayIso } from "../lib/format";
import { ErrorNote, Field, Modal } from "./components/ui";
import { useAction, useAsync } from "./useAsync";

type Kind = "logs" | "photos";
type Named = { id: number; name: string };

/** Values of the Journal filters the dialog starts from (same keys as the page form). */
export type PurgeStart = Partial<Record<"from" | "to" | "employee_id" | "department_id" | "entity_id" | "zone_id", string>>;

/**
 * Bulk deletion (data.purge, SRS FR-97 / FR-98): filters, then the number of lines with a summary,
 * then an explicit confirmation. The server writes the purge in the audit, which is never deletable.
 */
export function PurgeDialog({ start = {}, onClose, onDone }: { start?: PurgeStart; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const employees = useAsync(() => admin.employees(), []);
  const entities = useAsync(() => admin.entities(), []);
  const departments = useAsync(() => admin.departments(), []);
  const zones = useAsync(() => admin.zones(), []);
  const [kind, setKind] = useState<Kind>("logs");
  const [form, setForm] = useState<PurgeStart>(start);
  const [archivedOnly, setArchivedOnly] = useState(false);
  const [count, setCount] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [deleted, setDeleted] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);

  const reset = () => { setCount(null); setConfirmed(false); setError(null); };
  const set = (key: keyof PurgeStart) => (e: { target: { value: string } }) => { setForm({ ...form, [key]: e.target.value }); reset(); };
  const num = (key: keyof PurgeStart) => (form[key] ? Number(form[key]) : undefined);
  const name = (list: Named[] | null | undefined, key: keyof PurgeStart) => list?.find((x) => x.id === num(key))?.name;
  const employee = employees.data?.find((e) => e.id === num("employee_id"));

  // Summary shown before the confirmation: what will be deleted, in the words of the screen.
  const summary: string[] = [];
  if (kind === "logs") {
    if (form.from) summary.push(tx("Du {0}", [form.from.split("-").reverse().join("/")]));
    if (form.to) summary.push(tx("Au {0}", [form.to.split("-").reverse().join("/")]));
    if (employee) summary.push(`${tx("Employé")} : ${employee.first_name} ${employee.last_name}`);
  }
  const department = name(departments.data, "department_id");
  const entity = name(entities.data, "entity_id");
  if (entity) summary.push(`${tx("Entité")} : ${entity}`);
  if (department) summary.push(`${tx("Département")} : ${department}`);
  if (kind === "logs") {
    const zone = name(zones.data, "zone_id");
    if (zone) summary.push(`${tx("Zone")} : ${zone}`);
  } else if (archivedOnly) {
    summary.push(tx("Employés archivés seulement"));
  }

  const logsBody = (dryRun: boolean): PurgeRequest => ({
    date_from: form.from ? startOfDayIso(form.from) : undefined,
    date_to: form.to ? endOfDayIso(form.to) : undefined,
    employee_id: num("employee_id"), department_id: num("department_id"), entity_id: num("entity_id"),
    zone_id: num("zone_id"), dry_run: dryRun,
  });
  const photosBody = (dryRun: boolean): PhotoPurgeRequest => ({
    department_id: num("department_id"), entity_id: num("entity_id"), archived_only: archivedOnly, dry_run: dryRun,
  });
  const call = (dryRun: boolean) => (kind === "logs" ? admin.purge(logsBody(dryRun)) : admin.purgePhotos(photosBody(dryRun)));

  const preview = () => act(async () => setCount((await call(true)).deleted));
  const remove = () => {
    setBusy(true);
    void act(async () => setDeleted((await call(false)).deleted)).finally(() => setBusy(false));
  };

  const noun = kind === "logs" ? tx("passage(s)") : tx("photo(s)");
  if (deleted !== null) {
    return (
      <Modal title={tx("Suppression en lot")} onClose={onDone}>
        <div className="form">
          <p className="note ok-note" role="status"><strong>{deleted}</strong>{" "}{kind === "logs" ? tx("passage(s) supprimé(s).") : tx("photo(s) supprimée(s).")}</p>
          <p className="muted">{tx("La suppression est inscrite dans l'audit (auteur, filtres, nombre de lignes).")}</p>
          <footer><button className="primary" onClick={onDone}>{tx("Fermer")}</button></footer>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={tx("Suppression en lot")} onClose={onClose}>
      <div className="form">
        <div className="tabs" role="tablist">
          {(["logs", "photos"] as Kind[]).map((k) => (
            <button key={k} type="button" role="tab" aria-selected={kind === k} className={kind === k ? "active" : ""}
              onClick={() => { setKind(k); reset(); }}>
              {k === "logs" ? tx("Passages du journal") : tx("Photos des employés")}
            </button>
          ))}
        </div>
        <p className="muted">
          {kind === "logs"
            ? tx("Les passages qui correspondent à tous les filtres choisis seront supprimés définitivement.")
            : tx("Les photos des employés qui correspondent à tous les filtres choisis seront retirées définitivement.")}
        </p>
        {kind === "logs" && (
          <>
            <div className="row">
              <Field label={tx("Du")}><input type="date" value={form.from ?? ""} onChange={set("from")} /></Field>
              <Field label={tx("Au")}><input type="date" value={form.to ?? ""} onChange={set("to")} /></Field>
            </div>
            <Field label={tx("Employé")}>
              <select value={form.employee_id ?? ""} onChange={set("employee_id")}>
                <option value="">{tx("Tous")}</option>
                {employees.data?.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name} ({e.matricule})</option>)}
              </select>
            </Field>
          </>
        )}
        <Field label={tx("Entité")}>
          <select value={form.entity_id ?? ""} onChange={set("entity_id")}>
            <option value="">{tx("Toutes")}</option>
            {entities.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </Field>
        <Field label={tx("Département")}>
          <select value={form.department_id ?? ""} onChange={set("department_id")}>
            <option value="">{tx("Tous")}</option>
            {departments.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </Field>
        {kind === "logs" ? (
          <Field label={tx("Zone")}>
            <select value={form.zone_id ?? ""} onChange={set("zone_id")}>
              <option value="">{tx("Toutes")}</option>
              {zones.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </Field>
        ) : (
          <label className="check">
            <input type="checkbox" checked={archivedOnly} onChange={(e) => { setArchivedOnly(e.target.checked); reset(); }} />
            {" "}{tx("Employés archivés seulement")}
          </label>
        )}

        {count !== null && (
          <div className="note" role="status">
            <p><strong>{count}</strong>{" "}{tx("{0} concerné(s).", [noun])}</p>
            <ul>{summary.map((line) => <li key={line}>{line}</li>)}</ul>
            {count > 0 && (
              <label className="check">
                <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
                {" "}{tx("Je confirme la suppression définitive de ces {0} {1}", [count, noun])}
              </label>
            )}
          </div>
        )}
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          {count === null ? (
            <button className="primary" disabled={summary.length === 0} onClick={preview}>{tx("Compter")}</button>
          ) : (
            <button className="danger" disabled={!confirmed || count === 0 || busy} onClick={remove}>
              {busy ? tx("Traitement…") : tx("Supprimer définitivement")}
            </button>
          )}
        </footer>
      </div>
    </Modal>
  );
}

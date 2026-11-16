import { type FormEvent, useMemo, useState } from "react";
import type { BulkAction, BulkRequest, BulkResult, Zone } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { tx } from "../i18n";
import { ErrorNote, Field, Modal } from "./components/ui";
import { useAction, useAsync } from "./useAsync";

/** The right each action needs (same as one by one). */
export const BULK_RIGHT: Record<BulkAction, string> = {
  org: "employees.edit",
  suspend: "employees.edit",
  reactivate: "employees.edit",
  archive: "employees.archive",
  add_zones: "authorizations.manage",
  remove_zones: "authorizations.manage",
};

const TITLE: Record<BulkAction, string> = {
  org: tx("Changer l'entité ou le département"),
  suspend: tx("Suspendre"),
  reactivate: tx("Réactiver"),
  archive: tx("Archiver"),
  add_zones: tx("Ajouter des zones"),
  remove_zones: tx("Retirer des zones"),
};

const KEEP = "keep";
const NONE = "none";

/** Same change for the selected employees (SRS FR-28). */
export function BulkDialog({ action, employeeIds, onClose, onDone }: {
  action: BulkAction; employeeIds: number[]; onClose: () => void; onDone: () => void;
}) {
  const { admin } = useAuth();
  const entities = useAsync(() => (action === "org" ? admin.entities() : Promise.resolve([])), [action]);
  const departments = useAsync(() => (action === "org" ? admin.departments() : Promise.resolve([])), [action]);
  const [entity, setEntity] = useState(KEEP);
  const [department, setDepartment] = useState(KEEP);
  const [zoneIds, setZoneIds] = useState<number[]>([]);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<BulkResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const act = useAction(setError);
  const count = employeeIds.length;

  const body = (): BulkRequest => {
    const request: BulkRequest = { action, employee_ids: employeeIds };
    if (action === "org") {
      if (entity !== KEEP) request.entity_id = entity === NONE ? null : Number(entity);
      if (department !== KEEP) request.department_id = department === NONE ? null : Number(department);
    }
    if (action === "add_zones" || action === "remove_zones") request.zone_ids = zoneIds;
    if (action === "archive") request.reason = reason.trim();
    return request;
  };
  const ready = action === "org" ? entity !== KEEP || department !== KEEP
    : action === "archive" ? reason.trim().length >= 3
      : action === "add_zones" || action === "remove_zones" ? zoneIds.length > 0 : true;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    void act(async () => setResult(await admin.bulkEmployees(body()))).finally(() => setBusy(false));
  };

  if (result) return <BulkReport result={result} title={TITLE[action]} onClose={onDone} />;

  return (
    <Modal title={tx("{0} · {1} employé(s)", [TITLE[action], count])} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        {action === "org" && (
          <>
            <p className="muted">{tx("Seul ce que vous changez est appliqué ; le reste de chaque fiche ne bouge pas.")}</p>
            <Field label={tx("Entité")}>
              <select value={entity} onChange={(e) => setEntity(e.target.value)}>
                <option value={KEEP}>{tx("Ne pas changer")}</option>
                <option value={NONE}>{tx("Aucune (retirer)")}</option>
                {entities.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            </Field>
            <Field label={tx("Département")}>
              <select value={department} onChange={(e) => setDepartment(e.target.value)}>
                <option value={KEEP}>{tx("Ne pas changer")}</option>
                <option value={NONE}>{tx("Aucun (retirer)")}</option>
                {departments.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            </Field>
          </>
        )}
        {action === "suspend" && <p>{tx("Leur badge sera refusé à l'entrée (la sortie reste possible).")}</p>}
        {action === "reactivate" && <p>{tx("Leur badge redonnera accès à leurs zones.")}</p>}
        {action === "archive" && (
          <>
            <p>{tx("Ils quittent les listes et leurs badges sont révoqués immédiatement. Leur historique est conservé.")}</p>
            <Field label={tx("Motif (obligatoire)")}>
              <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={tx("Départ, fin de contrat…")}
                minLength={3} maxLength={300} autoFocus />
            </Field>
          </>
        )}
        {(action === "add_zones" || action === "remove_zones") && (
          <ZonePicker selected={zoneIds} onChange={setZoneIds} />
        )}
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className={action === "archive" ? "danger" : "primary"} disabled={!ready || busy}>
            {busy ? tx("Traitement…") : tx("Appliquer à {0} employé(s)", [count])}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

/** Zones given to (or removed from) everybody on staff in a department (SRS FR-42). */
export function DepartmentZonesDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const departments = useAsync(() => admin.departments(), []);
  const entities = useAsync(() => admin.entities(), []);
  const [department, setDepartment] = useState("");
  const [entity, setEntity] = useState("");
  const [mode, setMode] = useState<"add_zones" | "remove_zones">("add_zones");
  const [zoneIds, setZoneIds] = useState<number[]>([]);
  const [preview, setPreview] = useState<number | null>(null);
  const [result, setResult] = useState<BulkResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const act = useAction(setError);

  const request = (dryRun: boolean): BulkRequest => ({
    action: mode, zone_ids: zoneIds, dry_run: dryRun,
    in_department_id: Number(department), ...(entity ? { in_entity_id: Number(entity) } : {}),
  });
  const choose = (setter: (v: string) => void) => (value: string) => { setter(value); setPreview(null); };
  const count = () => {
    if (!department) return;
    void act(async () => setPreview((await admin.bulkEmployees(request(true))).total));
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    void act(async () => setResult(await admin.bulkEmployees(request(false)))).finally(() => setBusy(false));
  };

  if (result) return <BulkReport result={result} title={tx("Zones par département")} onClose={onDone} />;

  return (
    <Modal title={tx("Zones par département")} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <p className="muted">{tx("Pour tout l'effectif actuel d'un département (actifs et suspendus ; les archivés ne sont pas concernés). Les zones déjà données ou leurs restrictions horaires restent telles quelles.")}</p>
        <Field label={tx("Département")}>
          <select value={department} onChange={(e) => choose(setDepartment)(e.target.value)} required onBlur={count}>
            <option value="">{tx("Choisir…")}</option>
            {departments.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </Field>
        <Field label={tx("Limiter à une entité (facultatif)")}>
          <select value={entity} onChange={(e) => choose(setEntity)(e.target.value)} onBlur={count}>
            <option value="">{tx("Toutes les entités")}</option>
            {entities.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </Field>
        <fieldset className="reasons">
          <legend>{tx("Action")}</legend>
          <label className="reason"><input type="radio" checked={mode === "add_zones"} onChange={() => setMode("add_zones")} />{tx("Ajouter les zones")}</label>
          <label className="reason"><input type="radio" checked={mode === "remove_zones"} onChange={() => setMode("remove_zones")} />{tx("Retirer les zones")}</label>
        </fieldset>
        <ZonePicker selected={zoneIds} onChange={setZoneIds} />
        {department && (
          <p className="note" role="status">
            {preview === null
              ? <button type="button" className="link" onClick={count}>{tx("Compter les employés concernés")}</button>
              : tx("{0} employé(s) concerné(s).", [preview])}
          </p>
        )}
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary" disabled={!department || zoneIds.length === 0 || busy || preview === 0}>
            {busy ? tx("Traitement…") : mode === "add_zones" ? tx("Ajouter les zones") : tx("Retirer les zones")}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

/** Zones grouped by unit, to tick. */
function ZonePicker({ selected, onChange }: { selected: number[]; onChange: (ids: number[]) => void }) {
  const { admin } = useAuth();
  const zones = useAsync(() => admin.zones(), []);
  const units = useMemo(() => {
    const byUnit = new Map<string, Zone[]>();
    for (const zone of zones.data ?? []) byUnit.set(zone.unit_name, [...(byUnit.get(zone.unit_name) ?? []), zone]);
    return [...byUnit.entries()];
  }, [zones.data]);
  const toggle = (id: number, on: boolean) => onChange(on ? [...selected, id] : selected.filter((x) => x !== id));
  return (
    <fieldset className="zone-picker">
      <legend>{tx("Zones")}</legend>
      {units.map(([unit, list]) => (
        <div key={unit}>
          <strong>{unit}</strong>
          {list.map((zone) => (
            <label key={zone.id} className="check">
              <input type="checkbox" checked={selected.includes(zone.id)} onChange={(e) => toggle(zone.id, e.target.checked)} />
              {" "}{zone.name}{!zone.is_active && <span className="muted">{" "}({tx("désactivée")})</span>}
            </label>
          ))}
        </div>
      ))}
    </fieldset>
  );
}

/** What was done, what was already so, and who was refused (with the reason). */
function BulkReport({ result, title, onClose }: { result: BulkResult; title: string; onClose: () => void }) {
  return (
    <Modal title={title} onClose={onClose}>
      <div className="form">
        <p className={`note ${result.failed.length ? "" : "ok-note"}`} role="status">
          {tx("{0} modifié(s), {1} déjà à jour, {2} en échec, sur {3}.",
            [result.done, result.unchanged, result.failed.length, result.total])}
        </p>
        {result.failed.length > 0 && (
          <table className="cards">
            <thead><tr><th>{tx("Matricule")}</th><th>{tx("Problème")}</th></tr></thead>
            <tbody>
              {result.failed.map((f) => <tr key={f.employee_id}><td>{f.matricule}</td><td>{f.reason}</td></tr>)}
            </tbody>
          </table>
        )}
        <footer><button className="primary" onClick={onClose}>{tx("Terminer")}</button></footer>
      </div>
    </Modal>
  );
}

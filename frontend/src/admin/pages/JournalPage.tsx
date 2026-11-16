import { tx } from "../../i18n";
import { useState } from "react";
import type { Direction, Flag, LogEntry, LogFilters, Verdict } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { describeFlag, describeVerdict, ALL_FLAGS, ALL_VERDICTS } from "../../lib/verdicts";
import { downloadBlob, endOfDayIso, formatDateTime, openPdf, stamp, startOfDayIso } from "../../lib/format";
import { Empty, ErrorNote, PageHeader, VerdictPill } from "../components/ui";
import { useAction, useAsync } from "../useAsync";
import { PurgeDialog } from "../Purge";

const PAGE = 100;

export function JournalPage() {
  const { admin, can } = useAuth();
  const employees = useAsync(() => admin.employees(), []);
  const entities = useAsync(() => admin.entities(), []);
  const departments = useAsync(() => admin.departments(), []);
  const units = useAsync(() => admin.units(), []);
  const zones = useAsync(() => admin.zones(), []);
  const agents = useAsync(() => admin.agents(), []);
  const checkpoints = useAsync(() => admin.checkpoints(), []);

  const [form, setForm] = useState<Record<string, string>>({});
  const [applied, setApplied] = useState<LogFilters>({});
  const [extra, setExtra] = useState<LogEntry[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [purging, setPurging] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false); // phones only: filters folded by default
  const activeFilters = Object.values(applied).filter((v) => v !== undefined && v !== "").length;
  const act = useAction(setError);

  const logs = useAsync(async () => {
    setExtra([]);
    return admin.logs(applied, 0, PAGE);
  }, [applied]);

  const toFilters = (): LogFilters => {
    const num = (k: string) => (form[k] ? Number(form[k]) : undefined);
    return {
      employee_id: num("employee_id"), entity_id: num("entity_id"), department_id: num("department_id"),
      unit_id: num("unit_id"), agent_id: num("agent_id"),
      zone_id: num("zone_id"), checkpoint_id: num("checkpoint_id"),
      verdict: (form.verdict || undefined) as Verdict | undefined,
      direction: (form.direction || undefined) as Direction | undefined,
      flag: (form.flag || undefined) as Flag | undefined,
      method: (form.method || undefined) as LogFilters["method"],
      date_from: form.from ? startOfDayIso(form.from) : undefined,
      date_to: form.to ? endOfDayIso(form.to) : undefined,
    };
  };
  const set = (key: string) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  const rows = [...(logs.data ?? []), ...extra];
  const mayHaveMore = (logs.data?.length ?? 0) + extra.length >= PAGE && (extra.length === 0 ? (logs.data?.length ?? 0) === PAGE : extra.length % PAGE === 0);

  return (
    <>
      <PageHeader title={tx("Journal des passages")}>
        {can("data.export") && selectedIds.length > 0 && (
          <>
            <button title={tx("Exporter uniquement les lignes sélectionnées")}
              onClick={() => act(async () => downloadBlob(
                await admin.exportJournal(applied, "xlsx", selectedIds), `journal-selection-${stamp()}.xlsx`,
              ))}>
              {tx("Exporter la sélection en Excel ({0})", [selectedIds.length])}
            </button>
            <button title={tx("Imprimer uniquement les lignes sélectionnées")}
              onClick={() => act(async () => openPdf(
                await admin.exportJournal(applied, "pdf", selectedIds), `journal-selection-${stamp()}.pdf`,
              ))}>
              {tx("Imprimer la sélection ({0})", [selectedIds.length])}
            </button>
          </>
        )}
        {can("data.export") && (
          <>
            <button title={tx("Fichier Excel avec les filtres appliqués")}
              onClick={() => act(async () => downloadBlob(await admin.exportJournal(applied, "xlsx"), `journal-passages-${stamp()}.xlsx`))}>{tx("Exporter en Excel")}
            </button>
            <button title={tx("Version imprimable A4 paysage avec les filtres appliqués")}
              onClick={() => act(async () => openPdf(await admin.exportJournal(applied, "pdf"), `journal-passages-${stamp()}.pdf`))}>{tx("Imprimer / PDF")}
            </button>
          </>
        )}
        {can("data.purge") && <button className="danger" onClick={() => setPurging(true)}>{tx("Supprimer en lot…")}</button>}
      </PageHeader>

      <button className="filters-toggle" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}>
        {filtersOpen ? tx("Masquer les filtres") : tx("Filtres{0}", [activeFilters ? ` (${activeFilters} actif${activeFilters > 1 ? "s" : ""})` : ""])}
      </button>
      <section className={`panel filters${filtersOpen ? " open" : ""}`}>
        <label>{tx("Du")}<input type="date" value={form.from ?? ""} onChange={set("from")} /></label>
        <label>{tx("Au")}<input type="date" value={form.to ?? ""} onChange={set("to")} /></label>
        <label>{tx("Employé")}
          <select value={form.employee_id ?? ""} onChange={set("employee_id")}>
            <option value="">{tx("Tous")}</option>
            {employees.data?.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name} ({e.matricule})</option>)}
          </select>
        </label>
        <label>{tx("Entité")}
          <select value={form.entity_id ?? ""} onChange={set("entity_id")}>
            <option value="">{tx("Toutes")}</option>
            {entities.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label>{tx("Département")}
          <select value={form.department_id ?? ""} onChange={set("department_id")}>
            <option value="">{tx("Tous")}</option>
            {departments.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label>{tx("Unité")}
          <select value={form.unit_id ?? ""} onChange={set("unit_id")}>
            <option value="">{tx("Toutes")}</option>
            {units.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label>{tx("Agent au poste")}
          <select value={form.agent_id ?? ""} onChange={set("agent_id")}>
            <option value="">{tx("Tous")}</option>
            {agents.data?.map((x) => <option key={x.id} value={x.id}>{x.full_name}</option>)}
          </select>
        </label>
        <label>{tx("Zone")}
          <select value={form.zone_id ?? ""} onChange={set("zone_id")}>
            <option value="">{tx("Toutes")}</option>
            {zones.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label>{tx("Point de contrôle")}
          <select value={form.checkpoint_id ?? ""} onChange={set("checkpoint_id")}>
            <option value="">{tx("Tous")}</option>
            {checkpoints.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label>{tx("Résultat")}
          <select value={form.verdict ?? ""} onChange={set("verdict")}>
            <option value="">{tx("Tous")}</option>
            {ALL_VERDICTS.map((v) => <option key={v} value={v}>{describeVerdict(v).short}</option>)}
          </select>
        </label>
        <label>{tx("Sens")}
          <select value={form.direction ?? ""} onChange={set("direction")}>
            <option value="">{tx("Tous")}</option>
            <option value="ENTREE">{tx("Entrée")}</option>
            <option value="SORTIE">{tx("Sortie")}</option>
          </select>
        </label>
        <label>{tx("Alerte")}
          <select value={form.flag ?? ""} onChange={set("flag")}>
            <option value="">{tx("Toutes les lignes")}</option>
            {ALL_FLAGS.map((f) => <option key={f} value={f}>{describeFlag(f)}</option>)}
          </select>
        </label>
        <label>{tx("Saisie")}
          <select value={form.method ?? ""} onChange={set("method")}>
            <option value="">{tx("Toutes")}</option>
            <option value="QR">{tx("QR scanné")}</option>
            <option value="MANUEL">{tx("Matricule saisi")}</option>
            <option value="CONSOLE">{tx("Déblocage depuis la console")}</option>
          </select>
        </label>
        <div className="filter-actions">
          <button className="primary" onClick={() => { setSelectedIds([]); setApplied(toFilters()); }}>{tx("Filtrer")}</button>
          <button onClick={() => { setForm({}); setSelectedIds([]); setApplied({}); }}>{tx("Réinitialiser")}</button>
        </div>
      </section>

      <ErrorNote message={error ?? logs.error} />
      {logs.data?.length === 0 && <Empty>{tx("Aucun passage ne correspond à ces filtres.")}</Empty>}
      {rows.length > 0 && (
        <section className="panel flush">
          <label className="check batch-select">
            <input type="checkbox" aria-label={tx("Sélectionner toutes les lignes affichées")}
              checked={rows.every((row) => selectedIds.includes(row.id))}
              onChange={(event) => setSelectedIds(event.target.checked ? rows.map((row) => row.id) : [])} />
            {tx("Sélectionner toutes les lignes affichées")} ({rows.length})
          </label>
          <table className="cards">
            <thead><tr>
              <th />
              <th>{tx("Date et heure")}</th><th>{tx("Personne")}</th><th>{tx("Unité · zone")}</th>
              <th>{tx("Poste")}</th><th>{tx("Agent")}</th><th>{tx("Sens")}</th><th>{tx("Résultat")}</th><th>{tx("Alertes")}</th>
            </tr></thead>
            <tbody>
              {rows.map((l) => (
                <tr key={l.id}>
                  <td data-label={tx("Sélection")}><input type="checkbox" aria-label={tx("Sélectionner le passage {0}", [l.id])}
                    checked={selectedIds.includes(l.id)}
                    onChange={(event) => setSelectedIds((current) => event.target.checked
                      ? [...current, l.id]
                      : current.filter((id) => id !== l.id))} /></td>
                  <td>{formatDateTime(l.occurred_at)}</td>
                  <td>{l.employee_name ? <><strong>{l.employee_name}</strong><br /><span className="muted">{l.employee_matricule}</span></> : <span className="muted">{tx("QR inconnu")}</span>}</td>
                  <td>{l.unit_name}<br /><span className="muted">{l.zone_name}</span></td>
                  <td>
                    {l.method === "CONSOLE" ? <span className="method">{tx("Déblocage depuis la console")}</span> : l.checkpoint_name}
                    {l.method === "MANUEL" && <> <span className="method" title={tx("Le QR n'a pas pu être lu : l'agent a saisi le matricule")}>{tx("matricule saisi")}</span></>}
                    {l.device_name && <><br /><span className="muted">{l.device_name}</span></>}
                  </td>
                  <td>{l.agent_name ?? <span className="muted">–</span>}</td>
                  <td>{l.direction === "ENTREE" ? tx("Entrée") : tx("Sortie")}</td>
                  <td><VerdictPill verdict={l.verdict} /></td>
                  <td>{l.flags.map((f) => <span key={f} className="flag">{describeFlag(f)}</span>)}{l.reason && <span className="muted"> {l.reason}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {mayHaveMore && (
            <button className="more" onClick={() => act(async () => setExtra([...extra, ...(await admin.logs(applied, rows.length, PAGE))]))}>{tx("Charger plus")}
            </button>
          )}
        </section>
      )}

      {purging && (
        <PurgeDialog start={{ from: form.from, to: form.to, employee_id: form.employee_id, department_id: form.department_id,
          entity_id: form.entity_id, zone_id: form.zone_id }}
          onClose={() => setPurging(false)} onDone={() => { setPurging(false); void logs.reload(); }} />
      )}
    </>
  );
}

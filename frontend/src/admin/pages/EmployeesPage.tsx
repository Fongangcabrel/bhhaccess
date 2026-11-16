import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { BulkAction, Employee, EmployeeStatus, ImportCheck, ImportReport } from "../../api/types";
import { BULK_RIGHT, BulkDialog, DepartmentZonesDialog } from "../BulkEmployees";
import { useAuth } from "../../auth/AuthContext";
import { Empty, ErrorNote, Field, Modal, PageHeader } from "../components/ui";
import { downloadBlob, stamp } from "../../lib/format";
import { useAction, useAsync } from "../useAsync";

export function EmployeesPage() {
  const { admin, can } = useAuth();
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<Tab>("courants");
  const employees = useAsync(() => admin.employees(search, TABS[tab].status), [search, tab]);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkAction, setBulkAction] = useState<BulkAction | null>(null);
  const [departmentZones, setDepartmentZones] = useState(false);
  const navigate = useNavigate();
  const shown = employees.data ?? [];
  const allSelected = shown.length > 0 && shown.every((e) => selectedIds.includes(e.id));
  const actions = (Object.keys(BULK_RIGHT) as BulkAction[]).filter((a) => can(BULK_RIGHT[a])
    && (tab !== "archives" || a === "org"));
  const canSelect = tab !== "archives" && actions.length > 0;
  const toggle = (id: number, on: boolean) =>
    setSelectedIds((current) => (on ? [...current, id] : current.filter((x) => x !== id)));
  const changeView = (apply: () => void) => { setSelectedIds([]); apply(); };
  const [exportError, setExportError] = useState<string | null>(null);
  const exportList = async () => {
    setExportError(null);
    try {
      downloadBlob(await admin.exportEmployees("xlsx", search || undefined, TABS[tab].status), `employes-${stamp()}.xlsx`);
    } catch (e) {
      setExportError(e instanceof Error ? e.message : tx("Export impossible"));
    }
  };

  return (
    <>
      <PageHeader title={tx("Employés")}>
        {can("data.export") && (
          <button onClick={() => void exportList()} title={tx("Liste affichée (onglet et recherche) en Excel")}>{tx("Exporter en Excel")}</button>
        )}
        {can("authorizations.manage") && (
          <button onClick={() => setDepartmentZones(true)} title={tx("Ajouter ou retirer des zones pour tout un département")}>
            {tx("Zones par département")}
          </button>
        )}
        {can("employees.import") && <button onClick={() => setImporting(true)}>{tx("Importer Excel")}</button>}
        {can("employees.edit") && <button className="primary" onClick={() => setCreating(true)}>{tx("Nouvel employé")}</button>}
      </PageHeader>
      <div className="tabs" role="tablist">
        {(Object.keys(TABS) as Tab[]).map((key) => (
          <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""}
            onClick={() => changeView(() => setTab(key))}>
            {TABS[key].label}
          </button>
        ))}
      </div>
      <input
        className="search"
        placeholder={tx("Rechercher par nom, prénom ou matricule…")}
        value={search}
        onChange={(e) => { const value = e.target.value; changeView(() => setSearch(value)); }}
      />
      {canSelect && selectedIds.length > 0 && (
        <div className="bulk-bar" role="toolbar" aria-label={tx("Actions sur la sélection")}>
          <strong>{tx("{0} sélectionné(s)", [selectedIds.length])}</strong>
          {actions.map((action) => (
            <button key={action} type="button" className={`small${action === "archive" ? " danger" : ""}`}
              onClick={() => setBulkAction(action)}>{BULK_LABEL[action]}</button>
          ))}
          <button type="button" className="link" onClick={() => setSelectedIds([])}>{tx("Tout désélectionner")}</button>
        </div>
      )}
      <ErrorNote message={employees.error ?? exportError} />
      {employees.data?.length === 0 && <Empty>{search ? tx("Aucun employé ne correspond à la recherche.") : TABS[tab].empty}</Empty>}
      {!!employees.data?.length && (
        <section className="panel flush">
          <table className="clickable cards">
            <thead><tr>{canSelect && (
              <th className="select-col">
                <input type="checkbox" aria-label={tx("Sélectionner tous les employés affichés")} checked={allSelected}
                  onChange={(e) => setSelectedIds(e.target.checked ? shown.map((x) => x.id) : [])} />
              </th>
            )}<th>{tx("Matricule")}</th><th>{tx("Nom")}</th><th>{tx("Entité")}</th><th>{tx("Département")}</th><th>{tx("Fonction")}</th><th>{tx("Statut")}</th></tr></thead>
            <tbody>
              {employees.data.map((e) => (
                <tr key={e.id} onClick={() => navigate(`/admin/employes/${e.id}`)}
                  className={selectedIds.includes(e.id) ? "selected" : undefined}>
                  {canSelect && (
                    <td className="select-col" data-label={tx("Sélection")} onClick={(event) => event.stopPropagation()}>
                      <input type="checkbox" aria-label={tx("Sélectionner {0} {1}", [e.first_name, e.last_name])}
                        checked={selectedIds.includes(e.id)} onChange={(event) => toggle(e.id, event.target.checked)} />
                    </td>
                  )}
                  <td>{e.matricule}</td>
                  <td><strong>{e.first_name} {e.last_name}</strong></td>
                  <td>{e.entity_name ?? "–"}</td>
                  <td>{e.department_name ?? "–"}</td>
                  <td>{e.job_title ?? "–"}</td>
                  <td><span className={`status ${e.status}`}>{STATUS_LABEL[e.status]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {creating && <EmployeeForm onClose={() => setCreating(false)} onDone={() => { setCreating(false); void employees.reload(); }} />}
      {importing && <ImportDialog onClose={() => { setImporting(false); void employees.reload(); }} />}
      {bulkAction && (
        <BulkDialog action={bulkAction} employeeIds={selectedIds} onClose={() => setBulkAction(null)}
          onDone={() => { setBulkAction(null); setSelectedIds([]); void employees.reload(); }} />
      )}
      {departmentZones && (
        <DepartmentZonesDialog onClose={() => setDepartmentZones(false)}
          onDone={() => { setDepartmentZones(false); void employees.reload(); }} />
      )}
    </>
  );
}

type Tab = "courants" | "actifs" | "suspendus" | "archives";

const BULK_LABEL: Record<BulkAction, string> = {
  org: tx("Entité / département"),
  suspend: tx("Suspendre"),
  reactivate: tx("Réactiver"),
  add_zones: tx("Ajouter des zones"),
  remove_zones: tx("Retirer des zones"),
  archive: tx("Archiver"),
};

const TABS: Record<Tab, { label: string; status?: EmployeeStatus; empty: string }> = {
  courants: { label: tx("Tous"), empty: tx("Aucun employé. Créez-en un ou importez un fichier Excel.") },
  actifs: { label: tx("Actifs"), status: "ACTIF", empty: tx("Aucun employé actif.") },
  suspendus: { label: tx("Suspendus"), status: "SUSPENDU", empty: tx("Aucun employé suspendu.") },
  archives: { label: tx("Archivés"), status: "ARCHIVE", empty: tx("Aucun employé archivé.") },
};

export const STATUS_LABEL: Record<EmployeeStatus, string> = { ACTIF: tx("actif"), SUSPENDU: tx("suspendu"), ARCHIVE: tx("archivé") };

/** Create an employee, or edit one when ``employee`` is given (only changed fields are sent). */
export function EmployeeForm({ employee, onClose, onDone }: { employee?: Employee; onClose: () => void; onDone: () => void }) {
  const { admin, can } = useAuth();
  const [adding, setAdding] = useState<"entity" | "department" | null>(null);
  const [newName, setNewName] = useState("");
  const entities = useAsync(() => admin.entities(), []);
  const departments = useAsync(() => admin.departments(), []);
  const [form, setForm] = useState({
    matricule: employee?.matricule ?? "",
    last_name: employee?.last_name ?? "",
    first_name: employee?.first_name ?? "",
    job_title: employee?.job_title ?? "",
  });
  const [entityId, setEntityId] = useState(employee?.entity_id ? String(employee.entity_id) : "");
  const [departmentId, setDepartmentId] = useState(employee?.department_id ? String(employee.department_id) : "");
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const values = {
      matricule: form.matricule.trim(),
      last_name: form.last_name.trim(),
      first_name: form.first_name.trim(),
      job_title: form.job_title.trim() || null,
      entity_id: entityId ? Number(entityId) : null,
      department_id: departmentId ? Number(departmentId) : null,
    };
    if (!employee) {
      void act(() => admin.createEmployee(values), onDone);
      return;
    }
    const changes = Object.fromEntries(
      Object.entries(values).filter(([key, value]) => employee[key as keyof typeof values] !== value),
    );
    if (Object.keys(changes).length === 0) return onClose();
    void act(() => admin.updateEmployee(employee.id, changes), onDone);
  };
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });
  const addOrg = () =>
    act(async () => {
      if (adding === "entity") {
        const created = await admin.createEntity(newName.trim());
        await entities.reload();
        setEntityId(String(created.id));
      } else {
        const created = await admin.createDepartment(newName.trim());
        await departments.reload();
        setDepartmentId(String(created.id));
      }
    }, () => { setAdding(null); setNewName(""); });

  return (
    <Modal title={employee ? tx("Modifier {0} {1}", [employee.first_name, employee.last_name]) : tx("Nouvel employé")} onClose={onClose}>
      <form onSubmit={submit} className="form">
        <Field label={tx("Matricule")}><input value={form.matricule} onChange={set("matricule")} required autoFocus /></Field>
        {employee && form.matricule.trim() !== employee.matricule && (
          <p className="note warn-note">{tx("Le matricule est imprimé sur le badge : pensez à réimprimer le badge.")}</p>
        )}
        <div className="row">
          <Field label={tx("Nom")}><input value={form.last_name} onChange={set("last_name")} required /></Field>
          <Field label={tx("Prénom")}><input value={form.first_name} onChange={set("first_name")} required /></Field>
        </div>
        <Field label={tx("Fonction")}><input value={form.job_title} onChange={set("job_title")} /></Field>
        <div className="row">
          <Field label={tx("Entité")}>
            <select value={entityId} onChange={(e) => setEntityId(e.target.value)}>
              <option value="">–</option>
              {entities.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </Field>
          <Field label={tx("Département")}>
            <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              <option value="">–</option>
              {departments.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </Field>
        </div>
        {can("employees.edit") && !adding && (
          <p className="org-shortcuts">
            <button type="button" className="link" onClick={() => setAdding("entity")}>{tx("+ Nouvelle entité")}</button>
            <button type="button" className="link" onClick={() => setAdding("department")}>{tx("+ Nouveau département")}</button>
          </p>
        )}
        {adding && (
          <div className="inline org-add">
            <input value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={120} autoFocus
              aria-label={adding === "entity" ? tx("Nom de la nouvelle entité") : tx("Nom du nouveau département")}
              placeholder={adding === "entity" ? tx("Nom de la nouvelle entité") : tx("Nom du nouveau département")}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (newName.trim()) void addOrg(); } }} />
            <button type="button" className="primary small" disabled={!newName.trim()} onClick={() => void addOrg()}>{tx("Ajouter")}</button>
            <button type="button" className="small" onClick={() => { setAdding(null); setNewName(""); }}>{tx("Annuler")}</button>
          </div>
        )}
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary">{employee ? tx("Enregistrer") : tx("Créer")}</button>
        </footer>
      </form>
    </Modal>
  );
}

const MAX_IMPORT_MB = 5;

/** Two steps: check the file (nothing written), then create the conforming rows (SRS FR-26, FR-27). */
export function ImportDialog({ onClose }: { onClose: () => void }) {
  const { admin } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [createOrg, setCreateOrg] = useState(false);
  const [check, setCheck] = useState<ImportCheck | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const act = useAction(setError);
  const run = (task: () => Promise<void>) => {
    setBusy(true);
    void act(task).finally(() => setBusy(false));
  };

  const pick = (chosen: File | null) => {
    setCheck(null);
    setError(chosen && chosen.size > MAX_IMPORT_MB * 1024 * 1024
      ? tx("Fichier trop lourd : {0} Mo maximum.", [MAX_IMPORT_MB]) : null);
    setFile(chosen);
  };
  const verify = (event: FormEvent) => {
    event.preventDefault();
    if (file) run(async () => setCheck(await admin.checkImport(file, createOrg)));
  };
  const create = () => file && run(async () => setReport(await admin.importEmployees(file, createOrg)));
  const downloadTemplate = () => void act(async () => downloadBlob(await admin.importTemplate(), "modele-import-employes.xlsx"));
  const downloadRejected = () => file && void act(async () =>
    downloadBlob(await admin.importRejected(file, createOrg), `lignes-rejetees-${stamp()}.xlsx`));

  if (report) {
    return (
      <Modal title={tx("Importer des employés (Excel)")} onClose={onClose}>
        <div className="form">
          <p className="note ok-note" role="status">
            <strong>{report.created}</strong>{" "}{tx("employé(s) créé(s),")}{" "}<strong>{report.rejected.length}</strong>{" "}{tx("ligne(s) rejetée(s).")}
          </p>
          {report.created_entities.length > 0 && <p className="muted">{tx("Entités créées :")}{" "}{report.created_entities.join(", ")}</p>}
          {report.created_departments.length > 0 && <p className="muted">{tx("Départements créés :")}{" "}{report.created_departments.join(", ")}</p>}
          {report.rejected.length > 0 && (
            <p><button type="button" className="small" onClick={downloadRejected}>{tx("Télécharger les lignes refusées (Excel)")}</button></p>
          )}
          <ErrorNote message={error} />
          <footer><button className="primary" onClick={onClose}>{tx("Terminer")}</button></footer>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={tx("Importer des employés (Excel)")} onClose={onClose}>
      <form onSubmit={verify} className="form import-form">
        <ol className="steps" aria-label={tx("Étapes")}>
          <li className={check ? "done" : "on"}>{tx("1. Vérifier le fichier")}</li>
          <li className={check ? "on" : ""}>{tx("2. Créer les employés")}</li>
        </ol>
        <p className="muted">{tx("Colonnes attendues :")}{" "}<strong>{tx("Matricule, Nom, Prénom")}</strong>{" "}{tx("(obligatoires), Entité, Département, Fonction. Les autres colonnes sont conservées. Seules les lignes conformes sont créées.")}
          {" "}<button type="button" className="link" onClick={downloadTemplate}>{tx("Télécharger le modèle")}</button>
        </p>
        <Field label={tx("Fichier .xlsx ({0} Mo maximum)", [MAX_IMPORT_MB])}>
          <input type="file" accept=".xlsx" onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        </Field>
        <label className="check">
          <input type="checkbox" checked={createOrg} onChange={(e) => { setCreateOrg(e.target.checked); setCheck(null); }} />{" "}{tx("Créer les entités et départements qui n'existent pas")}
        </label>

        {check && <CheckSummary check={check} onDownloadRejected={downloadRejected} />}

        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          {!check ? (
            <button className="primary" disabled={!file || busy || !!error}>{busy ? tx("Vérification…") : tx("Vérifier le fichier")}</button>
          ) : (
            <button type="button" className="primary" disabled={busy || check.valid === 0} onClick={create}>
              {busy ? tx("Import…") : check.valid === 0 ? tx("Aucune ligne à créer") : tx("Créer {0} employé(s)", [check.valid])}
            </button>
          )}
        </footer>
      </form>
    </Modal>
  );
}

/** Result of the check: what will be created, and why the other rows are refused. */
function CheckSummary({ check, onDownloadRejected }: { check: ImportCheck; onDownloadRejected: () => void }) {
  return (
    <section className="import-check" aria-label={tx("Résultat de la vérification")}>
      <div className="import-counts">
        <span><strong>{check.total}</strong>{" "}{tx("ligne(s) lue(s)")}</span>
        <span className="ok"><strong>{check.valid}</strong>{" "}{tx("prête(s) à créer")}</span>
        <span className={check.rejected.length ? "bad" : ""}><strong>{check.rejected.length}</strong>{" "}{tx("refusée(s)")}</span>
      </div>
      <p className="muted">{tx("Rien n'a encore été enregistré.")}</p>
      {check.new_entities.length > 0 && <p className="muted">{tx("Entités qui seront créées :")}{" "}{check.new_entities.join(", ")}</p>}
      {check.new_departments.length > 0 && <p className="muted">{tx("Départements qui seront créés :")}{" "}{check.new_departments.join(", ")}</p>}
      {check.rejected.length > 0 && (
        <>
          <div className="panel-head">
            <h3>{tx("Lignes refusées")}</h3>
            <button type="button" className="small" onClick={onDownloadRejected}>{tx("Télécharger (Excel)")}</button>
          </div>
          <p className="muted">{tx("Le fichier reprend ces lignes avec une colonne « Erreurs » : corrigez-les puis importez-le.")}</p>
          <table className="cards">
            <thead><tr><th>{tx("Ligne")}</th><th>{tx("Matricule")}</th><th>{tx("Problème")}</th></tr></thead>
            <tbody>
              {check.rejected.slice(0, 50).map((r) => (
                <tr key={r.row}><td>{r.row}</td><td>{r.matricule ?? "–"}</td><td>{r.errors.join(" ; ")}</td></tr>
              ))}
            </tbody>
          </table>
          {check.rejected.length > 50 && <p className="muted">{tx("… et {0} autre(s) dans le fichier à télécharger.", [check.rejected.length - 50])}</p>}
        </>
      )}
      {check.preview.length > 0 && (
        <>
          <h3>{tx("Aperçu des employés à créer")}</h3>
          <table className="cards">
            <thead><tr><th>{tx("Matricule")}</th><th>{tx("Nom")}</th><th>{tx("Entité")}</th><th>{tx("Département")}</th><th>{tx("Fonction")}</th></tr></thead>
            <tbody>
              {check.preview.map((r) => (
                <tr key={r.row}>
                  <td>{r.matricule}</td><td>{r.first_name} {r.last_name}</td>
                  <td>{r.entity ?? "–"}</td><td>{r.department ?? "–"}</td><td>{r.job_title ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {check.valid > check.preview.length && <p className="muted">{tx("… et {0} autre(s).", [check.valid - check.preview.length])}</p>}
        </>
      )}
    </section>
  );
}

import { tx } from "../../i18n";
import { useState } from "react";
import type { AuditFilters, AuditRow } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { downloadBlob, endOfDayIso, formatDateTime, openPdf, stamp, startOfDayIso } from "../../lib/format";
import { Empty, ErrorNote, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

const PAGE = 100;
const SYSTEM = "system";

/** Categories of the filter: the prefix of the action code. */
const CATEGORIES: [string, string][] = [
  ["employee", tx("Employés")],
  ["badge", tx("Badges")],
  ["authorization", tx("Accès aux zones")],
  ["zone", tx("Zones")],
  ["unit", tx("Unités")],
  ["checkpoint", tx("Postes")],
  ["agent", tx("Agents")],
  ["device", tx("Téléphones")],
  ["presence", tx("Présences")],
  ["user", tx("Utilisateurs")],
  ["role", tx("Rôles et droits")],
  ["export", tx("Exports")],
  ["logs", tx("Purge du journal")],
];

/** Who did what, when, from where, and what changed (SRS FR-71). Read-only by design. */
export function AuditPage() {
  const { admin, can } = useAuth();
  const actors = useAsync(() => admin.auditActors(), []);
  const [form, setForm] = useState<Record<string, string>>({});
  const [applied, setApplied] = useState<AuditFilters>({});
  const [extra, setExtra] = useState<AuditRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const act = useAction(setError);
  const activeFilters = Object.values(applied).filter((v) => v !== undefined && v !== "" && v !== false).length;

  const lines = useAsync(async () => {
    setExtra([]);
    return admin.audit(applied, 0, PAGE);
  }, [applied]);

  const toFilters = (): AuditFilters => ({
    action: form.action || undefined,
    actor_id: form.actor && form.actor !== SYSTEM ? Number(form.actor) : undefined,
    system: form.actor === SYSTEM || undefined,
    target: form.target?.trim() || undefined,
    date_from: form.from ? startOfDayIso(form.from) : undefined,
    date_to: form.to ? endOfDayIso(form.to) : undefined,
  });
  const set = (key: string) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });
  const rows = [...(lines.data ?? []), ...extra];
  const mayHaveMore = rows.length > 0 && rows.length % PAGE === 0;
  const exportAs = (format: "xlsx" | "pdf") =>
    act(async () => {
      const blob = await admin.exportAudit(format, applied);
      if (format === "xlsx") downloadBlob(blob, `audit-${stamp()}.xlsx`);
      else openPdf(blob, `audit-${stamp()}.pdf`);
    });

  return (
    <>
      <PageHeader title={tx("Audit")}>
        {can("data.export") && (
          <>
            <button title={tx("Fichier Excel avec les filtres appliqués")} onClick={() => exportAs("xlsx")}>{tx("Exporter en Excel")}</button>
            <button title={tx("Version imprimable A4 paysage avec les filtres appliqués")} onClick={() => exportAs("pdf")}>{tx("Imprimer / PDF")}</button>
          </>
        )}
      </PageHeader>
      <p className="muted intro">{tx("Toutes les modifications faites dans la console : qui, quand, depuis quelle adresse, et ce qui a changé. Ce journal ne peut être ni modifié ni supprimé.")}
      </p>

      <button className="filters-toggle" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}>
        {filtersOpen ? tx("Masquer les filtres") : tx("Filtres{0}", [activeFilters ? ` (${activeFilters} actif${activeFilters > 1 ? "s" : ""})` : ""])}
      </button>
      <section className={`panel filters${filtersOpen ? " open" : ""}`}>
        <label>{tx("Du")}<input type="date" value={form.from ?? ""} onChange={set("from")} /></label>
        <label>{tx("Au")}<input type="date" value={form.to ?? ""} onChange={set("to")} /></label>
        <label>{tx("Catégorie")}
          <select value={form.action ?? ""} onChange={set("action")}>
            <option value="">{tx("Toutes")}</option>
            {CATEGORIES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
        <label>{tx("Auteur")}
          <select value={form.actor ?? ""} onChange={set("actor")}>
            <option value="">{tx("Tous")}</option>
            {actors.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            <option value={SYSTEM}>{tx("Téléphones / système")}</option>
          </select>
        </label>
        <label>{tx("Objet")}
          <input value={form.target ?? ""} onChange={set("target")} placeholder={tx("Matricule, zone, identifiant…")}
            onKeyDown={(e) => e.key === "Enter" && setApplied(toFilters())} />
        </label>
        <div className="filter-actions">
          <button className="primary" onClick={() => setApplied(toFilters())}>{tx("Filtrer")}</button>
          <button onClick={() => { setForm({}); setApplied({}); }}>{tx("Réinitialiser")}</button>
        </div>
      </section>

      <ErrorNote message={error ?? lines.error} />
      {lines.data?.length === 0 && <Empty>{tx("Aucune action ne correspond à ces filtres.")}</Empty>}
      {rows.length > 0 && (
        <section className="panel flush">
          <table className="cards audit">
            <thead><tr><th>{tx("Date et heure")}</th><th>{tx("Auteur")}</th><th>{tx("Action")}</th><th>{tx("Objet")}</th><th>{tx("Détail")}</th><th className="hide-sm">{tx("Adresse IP")}</th></tr></thead>
            <tbody>
              {rows.map((line) => (
                <tr key={line.id}>
                  <td>{formatDateTime(line.occurred_at)}</td>
                  <td>{line.actor_id ? line.actor_name : <span className="muted">{line.actor_name}</span>}</td>
                  <td><strong>{line.action_label}</strong></td>
                  <td>{line.target ?? <span className="muted">–</span>}</td>
                  <td><AuditDetail line={line} /></td>
                  <td className="hide-sm muted">{line.ip ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {mayHaveMore && (
            <button className="more" onClick={() => act(async () => setExtra([...extra, ...(await admin.audit(applied, rows.length, PAGE))]))}>{tx("Charger plus")}
            </button>
          )}
        </section>
      )}
    </>
  );
}

/** Before → after, one line per field that changed, then the rest (motif, filtres…). */
export function AuditDetail({ line }: { line: AuditRow }) {
  if (!line.changes.length && !line.other) return <span className="muted">–</span>;
  return (
    <div className="audit-detail">
      {line.changes.length > 0 && (
        <ul className="changes">
          {line.changes.map((c) => (
            <li key={c.field}>
              <span className="field-name">{c.label}</span>{" "}
              <del title={tx("Avant")}>{c.before_text}</del> <span aria-hidden="true">→</span>{" "}
              <ins title={tx("Après")}>{c.after_text}</ins>
            </li>
          ))}
        </ul>
      )}
      {line.other && <span className="muted">{line.other}</span>}
    </div>
  );
}

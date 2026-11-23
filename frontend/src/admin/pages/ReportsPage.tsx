import { tx } from "../../i18n";
import { useState } from "react";
import type { ReportFilters, ReportKind, TrendDay, Verdict } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { controlMode } from "../../lib/controlModes";
import { downloadBlob, endOfDayIso, formatDateTime, openPdf, stamp, startOfDayIso } from "../../lib/format";
import { describeVerdict } from "../../lib/verdicts";
import { Empty, ErrorNote, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

const TABS: { key: ReportKind; label: string; file: string }[] = [
  { key: "movements", label: tx("Mouvements"), file: "mouvements" },
  { key: "presence", label: tx("Présence par zone"), file: "presence-par-zone" },
  { key: "refusals", label: tx("Tendances des refus"), file: "tendances-refus" },
];

/** Rapport ▸ Rapports: movements per employee and zone (FR-73), presence by zone and refusal trends (FR-77). */
export function ReportsPage() {
  const { admin, can } = useAuth();
  const employees = useAsync(() => admin.employees(), []);
  const entities = useAsync(() => admin.entities(), []);
  const departments = useAsync(() => admin.departments(), []);
  const units = useAsync(() => admin.units(), []);
  const zones = useAsync(() => admin.zones(), []);

  const [tab, setTab] = useState<ReportKind>("movements");
  const [form, setForm] = useState<Record<string, string>>({});
  const [applied, setApplied] = useState<ReportFilters>({});
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const set = (key: string) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  const toFilters = (): ReportFilters => {
    const num = (k: string) => (form[k] ? Number(form[k]) : undefined);
    return {
      employee_id: num("employee_id"), entity_id: num("entity_id"), department_id: num("department_id"),
      unit_id: num("unit_id"), zone_id: num("zone_id"),
      date_from: form.from ? startOfDayIso(form.from) : undefined,
      date_to: form.to ? endOfDayIso(form.to) : undefined,
    };
  };
  const current = TABS.find((t) => t.key === tab)!;
  const exportAs = (format: "xlsx" | "pdf") => act(async () => {
    const blob = await admin.exportReport(tab, format, applied);
    const name = `${current.file}-${stamp()}.${format}`;
    if (format === "xlsx") downloadBlob(blob, name); else openPdf(blob, name);
  });

  return (
    <>
      <PageHeader title={tx("Rapports")}>
        {can("data.export") && (
          <>
            <button title={tx("Fichier Excel avec les filtres appliqués")} onClick={() => exportAs("xlsx")}>{tx("Exporter en Excel")}</button>
            <button title={tx("Version imprimable A4 paysage avec les filtres appliqués")} onClick={() => exportAs("pdf")}>{tx("Imprimer / PDF")}</button>
          </>
        )}
      </PageHeader>

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className={tab === t.key ? "active" : ""}
            onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>

      <section className="panel filters open">
        <label>{tx("Du")}<input type="date" value={form.from ?? ""} onChange={set("from")} /></label>
        <label>{tx("Au")}<input type="date" value={form.to ?? ""} onChange={set("to")} /></label>
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
        <label>{tx("Zone")}
          <select value={form.zone_id ?? ""} onChange={set("zone_id")}>
            <option value="">{tx("Toutes")}</option>
            {zones.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label>{tx("Employé")}
          <select value={form.employee_id ?? ""} onChange={set("employee_id")}>
            <option value="">{tx("Tous")}</option>
            {employees.data?.map((e) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name} ({e.matricule})</option>)}
          </select>
        </label>
        <div className="filter-actions">
          <button className="primary" onClick={() => setApplied(toFilters())}>{tx("Filtrer")}</button>
          <button onClick={() => { setForm({}); setApplied({}); }}>{tx("Réinitialiser")}</button>
        </div>
      </section>

      <ErrorNote message={error} />
      {tab === "movements" && <Movements filters={applied} />}
      {tab === "presence" && <PresenceByZone filters={applied} />}
      {tab === "refusals" && <RefusalTrends filters={applied} />}
    </>
  );
}

function Movements({ filters }: { filters: ReportFilters }) {
  const { admin } = useAuth();
  const report = useAsync(() => admin.movementReport(filters), [filters]);
  const data = report.data;
  return (
    <>
      <ErrorNote message={report.error} />
      {data && (
        <div className="kpis">
          <div className="kpi"><strong>{data.employees}</strong><span>{tx("Employés")}</span></div>
          <div className="kpi ok"><strong>{data.entries}</strong><span>{tx("Entrées")}</span></div>
          <div className="kpi exit"><strong>{data.exits}</strong><span>{tx("Sorties")}</span></div>
          <div className="kpi deny"><strong>{data.refused}</strong><span>{tx("Refus")}</span></div>
          <div className="kpi warn"><strong>{data.unblocks}</strong><span>{tx("Déblocages")}</span>
            <small>{tx("Corrections depuis la console, comptées à part des passages.")}</small></div>
        </div>
      )}
      {data?.rows.length === 0 && <Empty>{tx("Aucun mouvement pour ces filtres.")}</Empty>}
      {data && data.rows.length > 0 && (
        <section className="panel flush">
          <table className="cards">
            <thead><tr>
              <th>{tx("Personne")}</th><th>{tx("Entité · département")}</th><th>{tx("Unité · zone")}</th>
              <th className="num">{tx("Entrées")}</th><th className="num">{tx("Sorties")}</th>
              <th className="num">{tx("Refus")}</th><th className="num">{tx("Déblocages")}</th>
              <th>{tx("Premier passage")}</th><th>{tx("Dernier passage")}</th>
            </tr></thead>
            <tbody>
              {data.rows.map((m) => (
                <tr key={`${m.employee_id}-${m.zone_id}`}>
                  <td><strong>{m.full_name}</strong><br /><span className="muted">{m.matricule}</span></td>
                  <td>{m.entity_name ?? "–"}<br /><span className="muted">{m.department_name ?? "–"}</span></td>
                  <td>{m.unit_name}<br /><span className="muted">{m.zone_name}</span></td>
                  <td className="num">{m.entries}</td><td className="num">{m.exits}</td>
                  <td className="num">{m.refused}</td><td className="num">{m.unblocks}</td>
                  <td>{formatDateTime(m.first_at)}</td><td>{formatDateTime(m.last_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}

function PresenceByZone({ filters }: { filters: ReportFilters }) {
  const { admin } = useAuth();
  const report = useAsync(() => admin.presenceReport(filters), [filters]);
  const data = report.data;
  return (
    <>
      <ErrorNote message={report.error} />
      {data && (
        <div className="kpis">
          <div className="kpi inside"><strong>{data.inside_now}</strong><span>{tx("À l'intérieur maintenant")}</span>
            <small>{tx("Zones « Signalé » et « Sortie obligatoire » ; une zone « Libre » ne suit pas la présence.")}</small></div>
          <div className="kpi ok"><strong>{data.entries}</strong><span>{tx("Entrées")}</span></div>
          <div className="kpi exit"><strong>{data.exits}</strong><span>{tx("Sorties")}</span></div>
          <div className="kpi deny"><strong>{data.refused}</strong><span>{tx("Refus")}</span></div>
        </div>
      )}
      {data?.rows.length === 0 && <Empty>{tx("Aucune zone pour ces filtres.")}</Empty>}
      {data && data.rows.length > 0 && (
        <section className="panel flush">
          <table className="cards">
            <thead><tr>
              <th>{tx("Unité · zone")}</th><th>{tx("Contrôle des entrées")}</th>
              <th className="num">{tx("À l'intérieur maintenant")}</th><th className="num">{tx("Personnes entrées")}</th>
              <th className="num">{tx("Entrées")}</th><th className="num">{tx("Sorties")}</th><th className="num">{tx("Refus")}</th>
            </tr></thead>
            <tbody>
              {data.rows.map((z) => (
                <tr key={z.zone_id}>
                  <td>{z.unit_name}<br /><strong>{z.zone_name}</strong></td>
                  <td>{controlMode(z.mode).label}</td>
                  <td className="num">{z.inside_now ?? <span className="muted">{tx("non suivi")}</span>}</td>
                  <td className="num">{z.people}</td><td className="num">{z.entries}</td>
                  <td className="num">{z.exits}</td><td className="num">{z.refused}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}

const shortDay = (day: string) => `${day.slice(8, 10)}/${day.slice(5, 7)}`;

function RefusalTrends({ filters }: { filters: ReportFilters }) {
  const { admin } = useAuth();
  const report = useAsync(() => admin.refusalTrend(filters), [filters]);
  const data = report.data;
  const change = data && data.previous_total > 0
    ? Math.round(((data.total - data.previous_total) / data.previous_total) * 100) : null;
  return (
    <>
      <ErrorNote message={report.error} />
      {data && (
        <>
          <div className="kpis">
            <div className="kpi deny"><strong>{data.total}</strong><span>{tx("Refus sur la période")}</span>
              <small>{tx("Du {0} au {1}", [formatDateTime(data.date_from).slice(0, 10), formatDateTime(data.date_to).slice(0, 10)])}</small></div>
            <div className="kpi"><strong>{data.previous_total}</strong><span>{tx("Période précédente")}</span>
              <small>{change === null ? tx("Même durée, juste avant") : tx("{0} % par rapport à la période précédente", [change > 0 ? `+${change}` : change])}</small></div>
            <div className="kpi"><strong>{data.unknown_qr}</strong><span>{tx("QR non reconnus")}</span>
              <small>{tx("Refus sans personne identifiée.")}</small></div>
          </div>
          <TrendChart days={data.days} />
          {data.total === 0 && <Empty>{tx("Aucun refus sur cette période.")}</Empty>}
          {data.total > 0 && (
            <div className="report-grid">
              <section className="panel flush">
                <h2 className="panel-title">{tx("Par motif")}</h2>
                <table>
                  <tbody>
                    {Object.entries(data.by_verdict).map(([verdict, count]) => (
                      <tr key={verdict}><td>{describeVerdict(verdict as Verdict).short}</td><td className="num">{count}</td></tr>
                    ))}
                  </tbody>
                </table>
              </section>
              <section className="panel flush">
                <h2 className="panel-title">{tx("Par zone")}</h2>
                <table>
                  <tbody>
                    {data.by_zone.map((z) => (
                      <tr key={z.zone_id}><td>{z.unit_name} · <strong>{z.zone_name}</strong></td><td className="num">{z.count}</td></tr>
                    ))}
                  </tbody>
                </table>
              </section>
              <section className="panel flush">
                <h2 className="panel-title">{tx("Personnes les plus refusées")}</h2>
                <table>
                  <tbody>
                    {data.by_employee.map((p) => (
                      <tr key={p.employee_id}><td>{p.full_name} <span className="muted">{p.matricule}</span></td><td className="num">{p.count}</td></tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </div>
          )}
        </>
      )}
    </>
  );
}

/** Refusals per day: one bar per day (empty days kept), detail of the hovered / focused day above. */
function TrendChart({ days }: { days: TrendDay[] }) {
  const [active, setActive] = useState<TrendDay | null>(null);
  const max = Math.max(1, ...days.map((d) => d.total));
  const describe = (d: TrendDay) => {
    const parts = Object.entries(d.by_verdict).map(([v, n]) => `${describeVerdict(v as Verdict).short} ${n}`);
    return tx("{0} : {1} refus", [shortDay(d.day), d.total]) + (parts.length ? ` — ${parts.join(", ")}` : "");
  };
  const labelled = new Set([0, Math.floor((days.length - 1) / 2), days.length - 1]);
  return (
    <section className="panel trend">
      <h2 className="panel-title">{tx("Refus par jour")}</h2>
      <p className="trend-detail" aria-live="polite">{active ? describe(active) : tx("Survolez une barre pour le détail du jour.")}</p>
      <div className="trend-plot">
        <span className="trend-max" aria-hidden="true">{max}</span>
        <div className="trend-bars" role="list" onMouseLeave={() => setActive(null)}>
          {days.map((d, i) => (
            <div key={d.day} role="listitem" tabIndex={0} className="trend-col" aria-label={describe(d)}
              onMouseEnter={() => setActive(d)} onFocus={() => setActive(d)} onBlur={() => setActive(null)}>
              <span className={`trend-bar${active?.day === d.day ? " on" : ""}`}
                style={{ height: d.total ? `${Math.max(2, (d.total / max) * 100)}%` : 0 }} />
              {labelled.has(i) && <span className="trend-day" aria-hidden="true">{shortDay(d.day)}</span>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

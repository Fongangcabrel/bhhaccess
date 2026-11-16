import { tx } from "../../i18n";
import { type FormEvent, useEffect, useState } from "react";
import type { Flag, MonitorPerson, MonitorUnit, MonitorZone, Monitoring } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { controlMode } from "../../lib/controlModes";
import { formatDateTime } from "../../lib/format";
import { describeFlag, describeVerdict } from "../../lib/verdicts";
import { Empty, ErrorNote, Field, Modal, PageHeader, VerdictPill } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

const REFRESH_MS = 15000;

type Unblocking = { person: MonitorPerson; zone: MonitorZone };

/** Live supervision: who is inside, who left, zone by zone and unit by unit, refreshed every 15 s. */
export function DashboardPage() {
  const { admin } = useAuth();
  const [unitId, setUnitId] = useState<number | undefined>();
  const monitoring = useAsync(() => admin.monitoring(unitId), [unitId]);
  const latest = useAsync(() => admin.logs({ unit_id: unitId }, 0, 10), [unitId]);
  const units = useAsync(() => admin.units(), []);
  const [unblocking, setUnblocking] = useState<Unblocking | null>(null);

  const { reload: reloadMonitoring } = monitoring;
  const { reload: reloadLatest } = latest;
  useEffect(() => {
    const timer = window.setInterval(() => { void reloadMonitoring(); void reloadLatest(); }, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [reloadMonitoring, reloadLatest]);

  const data = monitoring.data;
  return (
    <>
      <PageHeader title={tx("Tableau de bord")}>
        <span className="muted live">
          <span className="dot" aria-hidden /> {data ? tx("À jour à {0}", [formatDateTime(data.generated_at)]) : tx("Chargement…")}{" "}{tx("· toutes les 15 s")}
        </span>
        {(units.data?.length ?? 0) > 1 && (
          <select aria-label={tx("Unité")} value={unitId ?? ""} onChange={(e) => setUnitId(e.target.value ? Number(e.target.value) : undefined)}>
            <option value="">{tx("Toutes les unités")}</option>
            {units.data?.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select>
        )}
      </PageHeader>
      <ErrorNote message={monitoring.error ?? latest.error} />

      {data && <Totals data={data} />}

      {data?.units.length === 0 && <Empty>{tx("Aucune unité configurée. Créez-en une dans « Unités et zones ».")}</Empty>}
      {data?.units.map((unit) => <UnitCard key={unit.unit_id} unit={unit} onUnblock={setUnblocking} />)}

      <div className="two-col">
        <section className="panel">
          <h2>{tx("Refus récents (aujourd'hui)")}</h2>
          {data?.recent_refusals.length === 0 && <Empty>{tx("Aucun refus aujourd'hui.")}</Empty>}
          {!!data?.recent_refusals.length && (
            <table className="cards">
              <thead><tr><th>{tx("Heure")}</th><th>{tx("Personne")}</th><th>{tx("Lieu")}</th><th>{tx("Motif")}</th></tr></thead>
              <tbody>
                {data.recent_refusals.map((r) => (
                  <tr key={r.log_id}>
                    <td>{formatDateTime(r.at)}</td>
                    <td>{r.employee_name ? <><strong>{r.employee_name}</strong><br /><span className="muted">{r.matricule}</span></> : <span className="muted">{tx("QR non reconnu")}</span>}</td>
                    <td>{r.zone_name}<br /><span className="muted">{r.checkpoint_name}{r.agent_name ? ` · ${r.agent_name}` : ""}</span></td>
                    <td>{describeVerdict(r.verdict).short}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          <h2>{tx("Postes de contrôle")}</h2>
          {data?.posts.length === 0 && <Empty>{tx("Aucun poste.")}</Empty>}
          {!!data?.posts.length && (
            <table className="cards">
              <thead><tr><th>{tx("Poste")}</th><th>{tx("Agent")}</th><th className="num">{tx("Scans")}</th><th>{tx("Dernier scan")}</th></tr></thead>
              <tbody>
                {data.posts.map((p) => (
                  <tr key={p.checkpoint_id} className={p.usable ? "" : "inactive"}>
                    <td>
                      <strong>{p.checkpoint_name}</strong>
                      <span className="pill">{p.direction === "ENTREE" ? tx("Entrée") : tx("Sortie")}</span>
                      {!p.usable && <span className="pill off">{tx("Désactivé")}</span>}
                      <br /><span className="muted">{p.unit_name} · {p.zone_name}</span>
                    </td>
                    <td>{p.agent_name ?? <span className="muted">—</span>}</td>
                    <td className="num">{p.scans_today}</td>
                    <td>{p.last_scan ? formatDateTime(p.last_scan) : <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>{tx("Derniers passages")}</h2>
        {latest.data?.length === 0 && <Empty>{tx("Aucun passage enregistré.")}</Empty>}
        {!!latest.data?.length && (
          <table className="cards">
            <thead><tr><th>{tx("Heure")}</th><th>{tx("Personne")}</th><th>{tx("Lieu")}</th><th>{tx("Agent")}</th><th>{tx("Résultat")}</th></tr></thead>
            <tbody>
              {latest.data.map((l) => (
                <tr key={l.id}>
                  <td>{formatDateTime(l.occurred_at)}</td>
                  <td>{l.employee_name ?? <span className="muted">{tx("QR non reconnu")}</span>}</td>
                  <td>{l.zone_name}<br /><span className="muted">{l.checkpoint_name}</span></td>
                  <td>{l.agent_name ?? <span className="muted">—</span>}</td>
                  <td><VerdictPill verdict={l.verdict} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {unblocking && (
        <UnblockDialog
          target={unblocking}
          onClose={() => setUnblocking(null)}
          onDone={() => { setUnblocking(null); void reloadMonitoring(); void reloadLatest(); }}
        />
      )}
    </>
  );
}

function Totals({ data }: { data: Monitoring }) {
  const t = data.totals;
  const flags = Object.entries(t.flags);
  const cards = [
    { label: tx("À l'intérieur"), value: t.inside, tone: "inside", note: tx("maintenant") },
    { label: tx("Sortis"), value: t.exited, tone: "exit", note: tx("aujourd'hui, pas revenus") },
    { label: tx("Entrées autorisées"), value: t.entries, tone: "ok", note: tx("aujourd'hui") },
    { label: tx("Refus"), value: t.refused, tone: "deny", note: t.unknown_qr ? tx("dont {0} QR non reconnu(s)", [t.unknown_qr]) : tx("aujourd'hui") },
    { label: tx("Anomalies"), value: t.anomalies, tone: t.anomalies ? "warn" : "neutral",
      note: flags.length ? flags.map(([f, n]) => `${describeFlag(f as Flag) ?? f} : ${n}`).join(" · ") : tx("aucune") },
  ];
  return (
    <section className="kpis">
      {cards.map((card) => (
        <div key={card.label} className={`kpi ${card.tone}`}>
          <strong>{card.value}</strong>
          <span>{card.label}</span>
          <small>{card.note}</small>
        </div>
      ))}
    </section>
  );
}

function UnitCard({ unit, onUnblock }: { unit: MonitorUnit; onUnblock: (target: Unblocking) => void }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section className="unit monitor">
      <header>
        <h3>{unit.unit_name}</h3>
        <div className="inline counts">
          <span className="count inside"><strong>{unit.inside}</strong>{" "}{tx("à l'intérieur")}</span>
          <span className="count exit"><strong>{unit.exited}</strong>{" "}{tx("sortis")}</span>
          <span className="count deny"><strong>{unit.refused}</strong>{" "}{tx("refus")}</span>
        </div>
      </header>
      {unit.zones.length === 0 ? <div className="body"><Empty>{tx("Aucune zone dans cette unité.")}</Empty></div> : (
        <div className="table-scroll">
          <table className="zones-table cards">
            <thead>
              <tr>
                <th>{tx("Zone")}</th><th className="num">{tx("À l'intérieur")}</th><th className="num">{tx("Sortis")}</th>
                <th className="num hide-sm">{tx("Entrées")}</th><th className="num hide-sm">{tx("Sorties")}</th><th className="num">{tx("Refus")}</th>
                <th className="hide-sm">{tx("Dernière activité")}</th><th />
              </tr>
            </thead>
            <tbody>
              {unit.zones.map((zone) => (
                <ZoneRows key={zone.zone_id} zone={zone} open={open === zone.zone_id}
                  onToggle={() => setOpen(open === zone.zone_id ? null : zone.zone_id)} onUnblock={onUnblock} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ZoneRows({ zone, open, onToggle, onUnblock }: {
  zone: MonitorZone; open: boolean; onToggle: () => void; onUnblock: (target: Unblocking) => void;
}) {
  const { can } = useAuth();
  const unblock = can("presence.unblock") && zone.mode !== "DESACTIVE";
  const people = zone.inside + zone.exited;
  return (
    <>
      <tr className={zone.is_active ? "" : "inactive"}>
        <td>
          <strong>{zone.zone_name}</strong>
          {zone.code && <span className="pill">{zone.code}</span>}
          {!zone.is_active && <span className="pill off">{tx("Désactivée")}</span>}
          <br /><span className="muted">{tx("Contrôle :")}{" "}{controlMode(zone.mode).label}</span>
        </td>
        <td className="num big inside">{zone.inside}</td>
        <td className="num big exit">{zone.exited}</td>
        <td className="num hide-sm">{zone.entries}</td>
        <td className="num hide-sm">{zone.exits}</td>
        <td className={`num${zone.refused ? " deny" : ""}`}>{zone.refused}</td>
        <td className="hide-sm">{zone.last_activity ? formatDateTime(zone.last_activity) : <span className="muted">—</span>}</td>
        <td className="right">
          <button className="small" onClick={onToggle} disabled={people === 0} aria-expanded={open}>
            {open ? tx("Masquer") : tx("Voir les personnes")}
          </button>
        </td>
      </tr>
      {open && (
        <tr className="detail">
          <td colSpan={8}>
            <div className="two-col tight">
              <PeopleList title={tx("À l'intérieur")} when={tx("Entré à")} people={zone.people_inside}
                action={unblock ? (person) => onUnblock({ person, zone }) : undefined} />
              <PeopleList title={tx("Sortis aujourd'hui")} when={tx("Sorti à")} people={zone.people_exited} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function PeopleList({ title, when, people, action }: {
  title: string; when: string; people: MonitorPerson[]; action?: (person: MonitorPerson) => void;
}) {
  return (
    <div>
      <h4>{title} ({people.length})</h4>
      {people.length === 0 ? <Empty>{tx("Personne.")}</Empty> : (
        <table className="cards">
          <thead><tr><th>{tx("Personne")}</th><th>{when}</th><th>{tx("Poste")}</th>{action && <th />}</tr></thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.employee_id}>
                <td><strong>{p.full_name}</strong><br /><span className="muted">{p.matricule}{p.department_name ? ` · ${p.department_name}` : ""}</span></td>
                <td>{formatDateTime(p.at)}</td>
                <td>{p.checkpoint_name ?? <span className="muted">—</span>}</td>
                {action && <td className="right"><button className="small" onClick={() => action(p)}>{tx("Débloquer")}</button></td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function UnblockDialog({ target, onClose, onDone }: { target: Unblocking; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [mode, setMode] = useState<"sortie" | "entree">("sortie");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const { person, zone } = target;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.unblock(person.employee_id, zone.zone_id, mode, reason.trim()), onDone);
  };

  return (
    <Modal title={tx("Débloquer {0}", [person.full_name])} onClose={onClose}>
      <form onSubmit={submit} className="form">
        <p className="muted">{zone.zone_name}{" "}{tx("· à l'intérieur depuis")}{" "}{formatDateTime(person.at)}</p>
        <Field label={tx("Action")}>
          <select value={mode} onChange={(e) => setMode(e.target.value as "sortie" | "entree")}>
            <option value="sortie">{tx("Enregistrer une sortie (la personne pourra rentrer)")}</option>
            <option value="entree">{tx("Enregistrer une entrée manuelle")}</option>
          </select>
        </Field>
        <Field label={tx("Motif (obligatoire, tracé dans l'audit)")}>
          <input value={reason} onChange={(e) => setReason(e.target.value)} minLength={3} required autoFocus />
        </Field>
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary" disabled={reason.trim().length < 3}>{tx("Débloquer")}</button>
        </footer>
      </form>
    </Modal>
  );
}

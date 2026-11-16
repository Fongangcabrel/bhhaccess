import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { formatDateTime } from "../../lib/format";
import type { Agent } from "../../api/types";
import { ActionsMenu, Empty, ErrorNote, Field, Modal, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

/** Agents are recorded, never logged in: the list feeds the reporting (who stood where, when). */
export function AgentsPage() {
  const { admin, can } = useAuth();
  const agents = useAsync(() => admin.agents(), []);
  const [selected, setSelected] = useState<number | undefined>();
  const history = useAsync(() => admin.assignments(selected), [selected]);
  const [fullName, setFullName] = useState("");
  const [matricule, setMatricule] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Agent | null>(null);
  const act = useAction(setError);
  const manage = can("zones.manage");
  const reloadAll = () => { void agents.reload(); void history.reload(); };

  const create = (event: FormEvent) => {
    event.preventDefault();
    void act(
      () => admin.createAgent(fullName.trim(), matricule.trim() || null),
      () => { setFullName(""); setMatricule(""); void agents.reload(); },
    );
  };

  return (
    <>
      <PageHeader title={tx("Agents")} />
      <p className="muted">{tx("Renseignez les agents et placez-les à leur poste depuis « Unités et zones ». L'historique alimente le journal : on sait qui était où, quand.")}
      </p>
      <ErrorNote message={error ?? agents.error} />

      {manage && (
        <form className="panel inline-form" onSubmit={create}>
          <input placeholder={tx("Nom complet")} value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          <input placeholder={tx("Matricule (facultatif)")} value={matricule} onChange={(e) => setMatricule(e.target.value)} style={{ maxWidth: 220 }} />
          <button className="primary">{tx("Ajouter l'agent")}</button>
        </form>
      )}

      <section className="panel flush">
        {agents.data?.length === 0 && <Empty>{tx("Aucun agent enregistré.")}</Empty>}
        {!!agents.data?.length && (
          <table className="cards">
            <thead><tr><th>{tx("Agent")}</th><th>{tx("Matricule")}</th><th>{tx("Poste actuel")}</th><th>{tx("État")}</th><th /></tr></thead>
            <tbody>
              {agents.data.map((a) => (
                <tr key={a.id}>
                  <td>{a.full_name}</td>
                  <td>{a.matricule ?? "–"}</td>
                  <td>
                    {a.posts.length === 0 && "–"}
                    {a.posts.map((p) => (
                      <div key={p.checkpoint_id}>
                        {p.unit_name} · {p.zone_name} · {p.checkpoint_name}
                        <span className="pill">{p.direction === "ENTREE" ? tx("Entrée") : tx("Sortie")}</span>
                      </div>
                    ))}
                  </td>
                  <td><span className={`status ${a.is_active ? "ACTIF" : "ARCHIVE"}`}>{a.is_active ? tx("Actif") : tx("Désactivé")}</span></td>
                  <td className="right">
                    <button className="small" onClick={() => setSelected(selected === a.id ? undefined : a.id)}>
                      {selected === a.id ? tx("Tout l'historique") : tx("Historique")}
                    </button>{" "}
                    {manage && (
                      <ActionsMenu label={a.full_name} actions={[
                        { label: tx("Modifier"), onClick: () => setEditing(a) },
                        { label: a.is_active ? tx("Désactiver (libère ses postes)") : tx("Réactiver"),
                          onClick: () => void act(() => admin.setAgentActive(a.id, !a.is_active), reloadAll) },
                        { label: tx("Supprimer"), danger: true, hint: tx("Possible seulement si l'agent n'a jamais été posté ; sinon désactivez-le"),
                          onClick: () => window.confirm(tx("Supprimer « {0} » ?", [a.full_name])) && void act(() => admin.deleteAgent(a.id), reloadAll) },
                      ]} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {editing && <EditAgent agent={editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); reloadAll(); }} />}

      <h3>{tx("Historique des affectations")}{selected ? tx(" (agent sélectionné)") : ""}</h3>
      <section className="panel flush">
        {history.data?.length === 0 && <Empty>{tx("Aucune affectation enregistrée.")}</Empty>}
        {!!history.data?.length && (
          <table className="cards">
            <thead><tr><th>{tx("Agent")}</th><th>{tx("Poste")}</th><th>{tx("Depuis")}</th><th>{tx("Jusqu'à")}</th></tr></thead>
            <tbody>
              {history.data.map((h) => (
                <tr key={h.id}>
                  <td>{h.agent_name}</td>
                  <td>{h.unit_name} · {h.zone_name} · {h.checkpoint_name}</td>
                  <td>{formatDateTime(h.started_at)}</td>
                  <td>{h.ended_at ? formatDateTime(h.ended_at) : tx("En cours")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

function EditAgent({ agent, onClose, onDone }: { agent: Agent; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [fullName, setFullName] = useState(agent.full_name);
  const [matricule, setMatricule] = useState(agent.matricule ?? "");
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.updateAgent(agent.id, fullName.trim(), matricule.trim() || null), onDone);
  };
  return (
    <Modal title={tx("Modifier l'agent")} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label={tx("Nom complet")}><input value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} autoFocus /></Field>
        <Field label={tx("Matricule (facultatif)")}><input value={matricule} onChange={(e) => setMatricule(e.target.value)} /></Field>
        <p className="muted">{tx("Le journal garde le nom de l'agent tel qu'il était au moment de chaque passage.")}</p>
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary">{tx("Enregistrer")}</button>
        </footer>
      </form>
    </Modal>
  );
}

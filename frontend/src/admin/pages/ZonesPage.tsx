import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import type { Agent, AntiPassbackMode, Checkpoint, Direction, Unit, Zone, ZoneSensitivity } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { CONTROL_MODES, controlMode } from "../../lib/controlModes";
import { ActionsMenu, Empty, ErrorNote, Field, Modal, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

const SENSITIVITY: Record<ZoneSensitivity, string> = { STANDARD: tx("Standard"), RESTREINTE: tx("Restreinte"), CRITIQUE: tx("Critique") };

type Editing =
  | { kind: "unit"; unit: Unit }
  | { kind: "zone"; zone: Zone }
  | { kind: "post"; post: Checkpoint };

export function ZonesPage() {
  const { admin, can } = useAuth();
  const units = useAsync(() => admin.units(), []);
  const checkpoints = useAsync(() => admin.checkpoints(), []);
  const agents = useAsync(() => admin.agents(), []);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Editing | null>(null);
  const act = useAction(setError);
  const [unitName, setUnitName] = useState("");
  const manage = can("zones.manage");

  const reloadAll = () => { void units.reload(); void checkpoints.reload(); void agents.reload(); };
  const createUnit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.createUnit(unitName.trim()), () => { setUnitName(""); reloadAll(); });
  };
  const done = () => { setEditing(null); reloadAll(); };

  return (
    <>
      <PageHeader title={tx("Unités et zones")} />
      <p className="muted">{tx("Une unité regroupe des zones. Dans la fiche d'un employé, on coche les zones autorisées unité par unité. Ce qui a déjà servi (passages, agents postés) ne se supprime pas : on le désactive, l'historique reste lisible.")}
      </p>
      <ErrorNote message={error ?? units.error} />

      {manage && (
        <form className="panel inline-form" onSubmit={createUnit}>
          <input placeholder={tx("Nouvelle unité (ex. Usine de Bonabéri)")} value={unitName} onChange={(e) => setUnitName(e.target.value)} required />
          <button className="primary">{tx("Créer l'unité")}</button>
        </form>
      )}

      {units.data?.length === 0 && <Empty>{tx("Aucune unité. Créez la première ci-dessus.")}</Empty>}
      {units.data?.map((unit) => (
        <UnitBlock
          key={unit.id}
          unit={unit}
          allUnits={units.data ?? []}
          checkpoints={checkpoints.data ?? []}
          agents={agents.data ?? []}
          onChange={reloadAll}
          onEdit={setEditing}
          onError={setError}
        />
      ))}

      {editing?.kind === "unit" && <UnitDialog unit={editing.unit} onClose={() => setEditing(null)} onDone={done} />}
      {editing?.kind === "zone" && <ZoneDialog zone={editing.zone} onClose={() => setEditing(null)} onDone={done} />}
      {editing?.kind === "post" && <PostDialog post={editing.post} onClose={() => setEditing(null)} onDone={done} />}
    </>
  );
}

interface BlockProps {
  onChange: () => void;
  onEdit: (editing: Editing) => void;
  onError: (message: string | null) => void;
}

function UnitBlock({ unit, allUnits, checkpoints, agents, onChange, onEdit, onError }: BlockProps & {
  unit: Unit;
  allUnits: Unit[];
  checkpoints: Checkpoint[];
  agents: Agent[];
}) {
  const { admin, can } = useAuth();
  const act = useAction(onError);
  const manage = can("zones.manage");
  const [name, setName] = useState("");
  const [mode, setMode] = useState<AntiPassbackMode>("DESACTIVE");
  const [warn, setWarn] = useState(false);

  const addZone = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.createZone(name.trim(), mode, unit.id, mode === "SOUPLE" && warn),
      () => { setName(""); setWarn(false); onChange(); });
  };
  const remove = () =>
    window.confirm(tx("Supprimer l'unité « {0} » ?", [unit.name])) && act(() => admin.deleteUnit(unit.id), onChange);

  return (
    <section className="unit">
      <header>
        <h3>{unit.name}</h3>
        <div className="inline">
          <span className="muted">{unit.zones.length > 1 ? tx("{0} zones", [unit.zones.length]) : tx("{0} zone", [unit.zones.length])}</span>
          {manage && (
            <ActionsMenu label={unit.name} actions={[
              { label: tx("Renommer l'unité"), onClick: () => onEdit({ kind: "unit", unit }) },
              { label: tx("Supprimer l'unité"), onClick: () => void remove(), danger: true, disabled: unit.zones.length > 0,
                hint: unit.zones.length > 0 ? tx("Déplacez ou supprimez d'abord ses zones") : undefined },
            ]} />
          )}
        </div>
      </header>
      <div className="body">
        {unit.zones.length === 0 && <Empty>{tx("Aucune zone dans cette unité.")}</Empty>}
        {unit.zones.map((zone) => (
          <ZoneBlock
            key={zone.id}
            zone={zone}
            units={allUnits}
            posts={checkpoints.filter((c) => c.zone_id === zone.id)}
            agents={agents}
            onChange={onChange}
            onEdit={onEdit}
            onError={onError}
          />
        ))}
        {manage && (
          <form className="inline" onSubmit={addZone} style={{ marginTop: ".6rem" }}>
            <input placeholder={tx("Nouvelle zone (ex. Atelier)")} value={name} onChange={(e) => setName(e.target.value)} required />
            <select value={mode} onChange={(e) => setMode(e.target.value as AntiPassbackMode)} aria-label={tx("Contrôle des entrées")}>
              {CONTROL_MODES.map((m) => <option key={m.value} value={m.value}>{tx("Contrôle des entrées :")}{" "}{m.label}</option>)}
            </select>
            {mode === "SOUPLE" && (
              <label className="check">
                <input type="checkbox" checked={warn} onChange={(e) => setWarn(e.target.checked)} />{" "}{tx("Avertir l'agent à l'écran")}
              </label>
            )}
            <button>{tx("Ajouter la zone")}</button>
          </form>
        )}
      </div>
    </section>
  );
}

function ZoneBlock({ zone, units, posts, agents, onChange, onEdit, onError }: BlockProps & {
  zone: Zone;
  units: Unit[];
  posts: Checkpoint[];
  agents: Agent[];
}) {
  const { admin, can } = useAuth();
  const act = useAction(onError);
  const manage = can("zones.manage");
  const [name, setName] = useState("");
  const [direction, setDirection] = useState<Direction>("ENTREE");
  const [placing, setPlacing] = useState<{ post: Checkpoint; agent: Agent } | null>(null);

  const placeAgent = (post: Checkpoint, value: string) => {
    if (!value) return void act(() => admin.assignAgent(post.id, null), onChange);
    const agent = agents.find((a) => a.id === Number(value));
    if (!agent) return;
    const elsewhere = agent.posts.filter((p) => p.checkpoint_id !== post.id);
    if (elsewhere.length === 0) return void act(() => admin.assignAgent(post.id, agent.id), onChange);
    setPlacing({ post, agent }); // ask: move here, or hold both posts
  };
  const confirmPlacing = (keep: boolean) => {
    if (!placing) return;
    const { post, agent } = placing;
    setPlacing(null);
    void act(() => admin.assignAgent(post.id, agent.id, keep), onChange);
  };

  const addPost = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.createCheckpoint(zone.id, name.trim(), direction), () => { setName(""); onChange(); });
  };
  const toggleZone = () => {
    if (zone.is_active && !window.confirm(tx("Désactiver « {0} » ? Ses postes ne pourront plus scanner.", [zone.name]))) return;
    void act(() => admin.updateZone(zone.id, { is_active: !zone.is_active }), onChange);
  };
  const removeZone = () =>
    window.confirm(tx("Supprimer la zone « {0} » et ses postes ?", [zone.name])) && act(() => admin.deleteZone(zone.id), onChange);
  const togglePost = (post: Checkpoint) =>
    act(() => admin.updateCheckpoint(post.id, { is_active: !post.is_active }), onChange);
  const removePost = (post: Checkpoint) =>
    window.confirm(tx("Supprimer le poste « {0} » ?", [post.name])) && act(() => admin.deleteCheckpoint(post.id), onChange);

  return (
    <div className={`zone-block${zone.is_active ? "" : " inactive"}`}>
      <div className="head">
        <span>
          <strong>{zone.name}</strong>
          {zone.code && <span className="pill">{zone.code}</span>}
          {zone.sensitivity !== "STANDARD" && <span className={`pill sens-${zone.sensitivity}`}>{SENSITIVITY[zone.sensitivity]}</span>}
          {!zone.is_active && <span className="pill off">{tx("Désactivée")}</span>}
          {zone.description && <small className="muted block">{zone.description}</small>}
        </span>
        <div className="inline">
          <select
            aria-label={tx("Contrôle des entrées de {0}", [zone.name])}
            title={controlMode(zone.antipassback_mode).hint}
            value={zone.antipassback_mode}
            disabled={!can("zones.antipassback")}
            onChange={(e) => act(() => admin.setZoneMode(zone.id, e.target.value as AntiPassbackMode), onChange)}
          >
            {CONTROL_MODES.map((m) => <option key={m.value} value={m.value}>{tx("Contrôle :")}{" "}{m.label}</option>)}
          </select>
          {manage && (
            <ActionsMenu label={zone.name} actions={[
              { label: tx("Modifier la zone"), onClick: () => onEdit({ kind: "zone", zone }) },
              ...units.filter((u) => u.id !== zone.unit_id).map((u) => ({
                label: tx("Déplacer vers « {0} »", [u.name]),
                onClick: () => void act(() => admin.moveZone(zone.id, u.id), onChange),
              })),
              { label: zone.is_active ? tx("Désactiver la zone") : tx("Réactiver la zone"), onClick: toggleZone },
              { label: tx("Supprimer la zone"), onClick: () => void removeZone(), danger: true },
            ]} />
          )}
        </div>
      </div>
      <p className="muted mode-hint">
        {controlMode(zone.antipassback_mode).hint}
        {zone.antipassback_mode === "SOUPLE" && (
          <label className="check warn-option" title={tx("L'agent voit un bandeau orange « Double entrée détectée » ; le passage reste autorisé")}>
            <input type="checkbox" checked={!!zone.antipassback_warn_agent} disabled={!can("zones.antipassback")}
              onChange={(e) => act(() => admin.setZoneMode(zone.id, "SOUPLE", e.target.checked), onChange)} />{" "}{tx("Avertir aussi l'agent à l'écran")}
          </label>
        )}
      </p>

      {posts.length === 0 && <Empty>{tx("Aucun poste de contrôle.")}</Empty>}
      {posts.map((post) => (
        <div className={`post${post.is_active ? "" : " inactive"}`} key={post.id}>
          <span className="name">
            {post.name}
            <span className="pill">{post.direction === "ENTREE" ? tx("Entrée") : tx("Sortie")}</span>
            {!post.is_active && <span className="pill off">{tx("Désactivé")}</span>}
          </span>
          <label className="inline">
            <span className="muted">{tx("Agent au poste")}</span>
            <select
              value={post.agent_id ?? ""}
              disabled={!manage || !post.usable}
              onChange={(e) => placeAgent(post, e.target.value)}
            >
              <option value="">{tx("— personne —")}</option>
              {agents
                .filter((a) => a.is_active || a.id === post.agent_id)
                .map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
            </select>
          </label>
          {manage && (
            <span className="post-actions">
              <ActionsMenu label={post.name} actions={[
                { label: tx("Modifier le poste"), onClick: () => onEdit({ kind: "post", post }) },
                { label: post.is_active ? tx("Désactiver le poste") : tx("Réactiver le poste"), onClick: () => void togglePost(post) },
                { label: tx("Supprimer le poste"), onClick: () => void removePost(post), danger: true },
              ]} />
            </span>
          )}
        </div>
      ))}
      {placing && (
        <Modal title={tx("Placer {0}", [placing.agent.full_name])} onClose={() => setPlacing(null)}>
          <div className="form">
            <p>
              {placing.agent.full_name}{" "}{tx("tient déjà :")}{" "}
              <strong>{placing.agent.posts.map((p) => `${p.checkpoint_name} (${p.direction === "ENTREE" ? tx("entrée") : "sortie"})`).join(", ")}</strong>.
            </p>
            <p className="muted">{tx("Une seule porte pour entrer et sortir ? Confiez-lui les deux postes. Pour une relève, déplacez-le : l'historique garde son passage au poste précédent.")}
            </p>
            <footer className="stack">
              <button type="button" onClick={() => setPlacing(null)}>{tx("Annuler")}</button>
              <button type="button" onClick={() => confirmPlacing(false)}>{tx("Déplacer ici")}</button>
              <button type="button" className="primary" onClick={() => confirmPlacing(true)}>{tx("Lui confier aussi «")}{" "}{placing.post.name} »
              </button>
            </footer>
          </div>
        </Modal>
      )}
      {manage && zone.is_active && (
        <form className="inline" onSubmit={addPost}>
          <input placeholder={tx("Nouveau poste (ex. Portail principal)")} value={name} onChange={(e) => setName(e.target.value)} required />
          <select value={direction} onChange={(e) => setDirection(e.target.value as Direction)} aria-label={tx("Sens")}>
            <option value="ENTREE">{tx("Entrée")}</option>
            <option value="SORTIE">{tx("Sortie")}</option>
          </select>
          <button className="small">{tx("Ajouter le poste")}</button>
        </form>
      )}
    </div>
  );
}

function DialogFooter({ onClose, label = tx("Enregistrer") }: { onClose: () => void; label?: string }) {
  return (
    <footer>
      <button type="button" onClick={onClose}>{tx("Annuler")}</button>
      <button className="primary">{label}</button>
    </footer>
  );
}

function UnitDialog({ unit, onClose, onDone }: { unit: Unit; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [name, setName] = useState(unit.name);
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.renameUnit(unit.id, name.trim()), onDone);
  };
  return (
    <Modal title={tx("Renommer l'unité")} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label={tx("Nom")}><input value={name} onChange={(e) => setName(e.target.value)} required autoFocus /></Field>
        <ErrorNote message={error} />
        <DialogFooter onClose={onClose} />
      </form>
    </Modal>
  );
}

function ZoneDialog({ zone, onClose, onDone }: { zone: Zone; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [form, setForm] = useState({
    name: zone.name, code: zone.code ?? "", description: zone.description ?? "", sensitivity: zone.sensitivity,
  });
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.updateZone(zone.id, {
      name: form.name.trim(), code: form.code.trim() || null,
      description: form.description.trim() || null, sensitivity: form.sensitivity,
    }), onDone);
  };
  return (
    <Modal title={tx("Modifier la zone « {0} »", [zone.name])} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <div className="row">
          <Field label={tx("Nom")}><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus /></Field>
          <Field label={tx("Code (facultatif)")}>
            <input value={form.code} maxLength={20} placeholder={tx("ex. DC-01")} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </Field>
        </div>
        <Field label={tx("Sensibilité")}>
          <select value={form.sensitivity} onChange={(e) => setForm({ ...form, sensitivity: e.target.value as ZoneSensitivity })}>
            {(Object.keys(SENSITIVITY) as ZoneSensitivity[]).map((s) => <option key={s} value={s}>{SENSITIVITY[s]}</option>)}
          </select>
        </Field>
        <Field label={tx("Description (facultatif)")}>
          <input value={form.description} maxLength={500} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        <p className="muted">{tx("Le contrôle des entrées se règle directement dans la liste.")}</p>
        <ErrorNote message={error} />
        <DialogFooter onClose={onClose} />
      </form>
    </Modal>
  );
}

function PostDialog({ post, onClose, onDone }: { post: Checkpoint; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [name, setName] = useState(post.name);
  const [direction, setDirection] = useState<Direction>(post.direction);
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.updateCheckpoint(post.id, { name: name.trim(), direction }), onDone);
  };
  return (
    <Modal title={tx("Modifier le poste « {0} »", [post.name])} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label={tx("Nom")}><input value={name} onChange={(e) => setName(e.target.value)} required autoFocus /></Field>
        <Field label={tx("Sens")}>
          <select value={direction} onChange={(e) => setDirection(e.target.value as Direction)}>
            <option value="ENTREE">{tx("Entrée")}</option>
            <option value="SORTIE">{tx("Sortie")}</option>
          </select>
        </Field>
        <ErrorNote message={error} />
        <DialogFooter onClose={onClose} />
      </form>
    </Modal>
  );
}

import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import type { OrgItem } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { ActionsMenu, Empty, ErrorNote, Field, Modal, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

type Kind = "entity" | "department";

const LABEL: Record<Kind, { title: string; one: string; placeholder: string; create: string; hint: string }> = {
  entity: {
    title: tx("Entités"), one: tx("l'entité"), placeholder: tx("Nouvelle entité"), create: tx("Créer l'entité"),
    hint: tx("Les sociétés ou structures du groupe."),
  },
  department: {
    title: tx("Départements"), one: tx("le département"), placeholder: tx("Nouveau département"),
    create: tx("Créer le département"), hint: tx("Les services ou directions, communs à toutes les entités."),
  },
};

const people = (n: number) => (n === 0 ? tx("aucun employé") : tx("{0} employé{1}", [n, n > 1 ? "s" : ""]));

/** The two lists offered in the employee form: an employee picks one entity and one department. */
export function OrgPage() {
  const { admin, can } = useAuth();
  const org = useAsync(() => admin.org(), []);
  const [renaming, setRenaming] = useState<{ kind: Kind; item: OrgItem } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const manage = can("employees.edit");
  const reload = () => void org.reload();

  return (
    <>
      <PageHeader title={tx("Entités et départements")} />
      <p className="muted intro">{tx("Deux listes indépendantes, proposées dans la fiche employé : chaque employé a une entité et un département. Un élément utilisé par des employés ne se supprime pas : renommez-le, ou changez d'abord ces employés.")}
      </p>
      <ErrorNote message={error ?? org.error} />
      <div className="two-col org-lists">
        {(["entity", "department"] as Kind[]).map((kind) => (
          <OrgList key={kind} kind={kind} items={kind === "entity" ? org.data?.entities : org.data?.departments}
            manage={manage} onChange={reload} onError={setError} onRename={(item) => setRenaming({ kind, item })} />
        ))}
      </div>
      {renaming && (
        <RenameDialog {...renaming} onClose={() => setRenaming(null)} onDone={() => { setRenaming(null); reload(); }} />
      )}
    </>
  );
}

function OrgList({ kind, items, manage, onChange, onError, onRename }: {
  kind: Kind; items: OrgItem[] | undefined; manage: boolean; onChange: () => void;
  onError: (m: string | null) => void; onRename: (item: OrgItem) => void;
}) {
  const { admin } = useAuth();
  const act = useAction(onError);
  const [name, setName] = useState("");
  const label = LABEL[kind];
  const create = (event: FormEvent) => {
    event.preventDefault();
    const value = name.trim();
    void act(() => (kind === "entity" ? admin.createEntity(value) : admin.createDepartment(value)),
      () => { setName(""); onChange(); });
  };
  const remove = (item: OrgItem) =>
    window.confirm(tx("Supprimer {0} « {1} » ?", [label.one, item.name])) &&
    act(() => (kind === "entity" ? admin.deleteEntity(item.id) : admin.deleteDepartment(item.id)), onChange);

  return (
    <section className="panel org-list">
      <div className="panel-head">
        <h2>{label.title}</h2>
        {items && <span className="muted">{items.length}</span>}
      </div>
      <p className="muted">{label.hint}</p>
      {manage && (
        <form className="inline" onSubmit={create}>
          <input placeholder={label.placeholder} value={name} onChange={(e) => setName(e.target.value)}
            aria-label={label.placeholder} required maxLength={120} />
          <button className="primary">{label.create}</button>
        </form>
      )}
      {items?.length === 0 && <Empty>{tx("Aucun élément pour l'instant.")}</Empty>}
      <ul className="org-items">
        {items?.map((item) => (
          <li key={item.id}>
            <span className="name">{item.name}</span>
            <span className="muted">{people(item.employees)}</span>
            {manage && (
              <ActionsMenu label={item.name} actions={[
                { label: tx("Renommer"), onClick: () => onRename(item) },
                { label: tx("Supprimer"), danger: true, disabled: item.employees > 0,
                  hint: item.employees > 0 ? tx("Des employés l'utilisent encore") : undefined,
                  onClick: () => void remove(item) },
              ]} />
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function RenameDialog({ kind, item, onClose, onDone }: { kind: Kind; item: OrgItem; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [name, setName] = useState(item.name);
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = name.trim();
    void act(() => (kind === "entity" ? admin.renameEntity(item.id, value) : admin.renameDepartment(item.id, value)), onDone);
  };
  return (
    <Modal title={tx("Renommer {0}", [LABEL[kind].one])} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label={tx("Nom")}><input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoFocus /></Field>
        <p className="muted">{tx("Le nouveau nom apparaît aussitôt sur les fiches, dans le journal et les exports.")}</p>
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary">{tx("Enregistrer")}</button>
        </footer>
      </form>
    </Modal>
  );
}

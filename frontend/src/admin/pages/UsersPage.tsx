import { tx } from "../../i18n";
import { Fragment, type FormEvent, useState } from "react";
import type { Role, UserRow } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { PasswordInput } from "../../components/PasswordInput";
import { PERMISSION_GROUPS } from "../../lib/permissions";
import { ErrorNote, Field, Modal, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

type Tab = "accounts" | "roles";

export function UsersPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>("accounts");
  return (
    <>
      <PageHeader title={tx("Utilisateurs et droits")} />
      <div className="tabs">
        <button className={tab === "accounts" ? "active" : ""} onClick={() => setTab("accounts")}>{tx("Comptes")}</button>
        {can("roles.assign") && <button className={tab === "roles" ? "active" : ""} onClick={() => setTab("roles")}>{tx("Rôles")}</button>}
      </div>
      {tab === "accounts" ? <Accounts /> : <Roles />}
    </>
  );
}

function Accounts() {
  const { admin, can, user: me } = useAuth();
  const users = useAsync(() => admin.users(), []);
  const roles = useAsync(() => admin.roles(), []);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [resetting, setResetting] = useState<UserRow | null>(null);
  const act = useAction(setError);
  const roleName = (id: number) => roles.data?.find((r) => r.id === id)?.label ?? "–";

  return (
    <>
      <div className="actions-row">
        <button className="primary" onClick={() => setCreating(true)}>{tx("Nouveau compte")}</button>
      </div>
      <ErrorNote message={error ?? users.error} />
      <section className="panel flush">
        <table className="cards">
          <thead><tr><th>{tx("Identifiant")}</th><th>{tx("Nom")}</th><th>{tx("Rôle")}</th><th>{tx("Exceptions")}</th><th>{tx("Statut")}</th><th /></tr></thead>
          <tbody>
            {users.data?.map((u) => (
              <tr key={u.id}>
                <td><strong>{u.username}</strong></td>
                <td>{u.full_name}</td>
                <td>{roleName(u.role_id)}</td>
                <td>{u.overrides.length ? tx("{0} droit(s) personnalisé(s)", [u.overrides.length]) : "–"}</td>
                <td>
                  <span className={`status ${u.is_active ? "ACTIF" : "ARCHIVE"}`}>{u.is_active ? tx("actif") : tx("désactivé")}</span>
                  {u.must_change_password && <span className="pill">{tx("Mot de passe temporaire")}</span>}
                </td>
                <td className="right">
                  {u.id !== me?.id && can("roles.assign") && <button className="small" onClick={() => setEditing(u)}>{tx("Droits")}</button>}{" "}
                  {u.id !== me?.id && <button className="small" onClick={() => setResetting(u)}>{tx("Mot de passe")}</button>}{" "}
                  {u.id !== me?.id && (
                    <button className="small" onClick={() => act(() => admin.setUserActive(u.id, !u.is_active), () => void users.reload())}>
                      {u.is_active ? tx("Désactiver") : tx("Réactiver")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {creating && roles.data && (
        <CreateUser roles={roles.data} onClose={() => setCreating(false)} onDone={() => { setCreating(false); void users.reload(); }} />
      )}
      {resetting && (
        <ResetPassword user={resetting} onClose={() => setResetting(null)}
          onDone={() => { setResetting(null); void users.reload(); }} />
      )}
      {editing && roles.data && (
        <RightsDialog
          user={users.data?.find((u) => u.id === editing.id) ?? editing}
          roles={roles.data}
          onChanged={() => void users.reload()}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}

function CreateUser({ roles, onClose, onDone }: { roles: Role[]; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [form, setForm] = useState({ username: "", full_name: "", password: "", role_id: String(roles.find((r) => r.name === "agent")?.id ?? roles[0]?.id ?? "") });
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.createUser({ ...form, role_id: Number(form.role_id) }), onDone);
  };
  return (
    <Modal title={tx("Nouveau compte")} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label={tx("Identifiant")}><input value={form.username} onChange={set("username")} minLength={3} required autoFocus /></Field>
        <Field label={tx("Nom complet")}><input value={form.full_name} onChange={set("full_name")} required /></Field>
        <Field label={tx("Mot de passe temporaire (la personne le changera à sa 1re connexion)")}>
          <PasswordInput value={form.password} onChange={set("password")} minLength={8} autoComplete="new-password" required />
        </Field>
        <p className="muted">{tx("8 caractères minimum, au moins une lettre et un chiffre.")}</p>
        <Field label={tx("Rôle")}>
          <select value={form.role_id} onChange={set("role_id")}>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select>
        </Field>
        <ErrorNote message={error} />
        <footer><button type="button" onClick={onClose}>{tx("Annuler")}</button><button className="primary">{tx("Créer")}</button></footer>
      </form>
    </Modal>
  );
}

/** Role of the person + per-right exceptions: inherited / allow / deny. */
function RightsDialog({ user, roles, onChanged, onClose }: { user: UserRow; roles: Role[]; onChanged: () => void; onClose: () => void }) {
  const { admin } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const role = roles.find((r) => r.id === user.role_id);
  const inherited = new Set(role?.permissions);
  const stateOf = (key: string) => user.overrides.find((o) => o.permission === key)?.effect ?? "inherit";

  const change = (key: string, value: string) =>
    act(
      () => (value === "inherit" ? admin.clearOverride(user.id, key) : admin.setOverride(user.id, key, value as "allow" | "deny")),
      onChanged,
    );

  return (
    <Modal title={tx("Droits de {0}", [user.full_name])} onClose={onClose}>
      <div className="form">
        <Field label={tx("Rôle (modèle de droits)")}>
          <select value={user.role_id} onChange={(e) => act(() => admin.setUserRole(user.id, Number(e.target.value)), onChanged)}>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select>
        </Field>
        <p className="muted">{tx("Pour chaque droit : « Selon le rôle », ou une exception pour cette personne seulement.")}</p>
        <ErrorNote message={error} />
        <div className="rights">
          {PERMISSION_GROUPS.map((group) => (
            <div key={group.title}>
              <h3>{group.title}</h3>
              {group.items.map((item) => (
                <div className="right-row" key={item.key}>
                  <span>{item.label}<small>{inherited.has(item.key) ? tx("inclus dans le rôle") : tx("non inclus")}</small></span>
                  <select value={stateOf(item.key)} onChange={(e) => change(item.key, e.target.value)}>
                    <option value="inherit">{tx("Selon le rôle")}</option>
                    <option value="allow">{tx("Autoriser")}</option>
                    <option value="deny">{tx("Refuser")}</option>
                  </select>
                </div>
              ))}
            </div>
          ))}
        </div>
        <footer><button className="primary" onClick={onClose}>{tx("Fermer")}</button></footer>
      </div>
    </Modal>
  );
}

function Roles() {
  const { admin, can } = useAuth();
  const roles = useAsync(() => admin.roles(), []);
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const editable = can("roles.manage");

  const toggle = (role: Role, key: string) => {
    const next = role.permissions.includes(key) ? role.permissions.filter((p) => p !== key) : [...role.permissions, key];
    void act(() => admin.updateRole(role.id, next), () => void roles.reload());
  };

  return (
    <>
      <p className="muted">{tx("Un changement de rôle s'applique tout de suite à toutes les personnes qui l'ont. Le rôle Super admin est fixe.")}</p>
      <ErrorNote message={error ?? roles.error} />
      <section className="panel flush scroll">
        <table className="matrix">
          <thead><tr><th>{tx("Droit")}</th>{roles.data?.map((r) => <th key={r.id}>{r.label}</th>)}</tr></thead>
          <tbody>
            {PERMISSION_GROUPS.map((group) => (
              <Fragment key={group.title}>
                <tr className="group-row"><td colSpan={(roles.data?.length ?? 0) + 1}>{group.title}</td></tr>
                {group.items.map((item) => (
                  <tr key={item.key}>
                    <td>{item.label}</td>
                    {roles.data?.map((r) => (
                      <td key={r.id} className="center-cell">
                        <input type="checkbox" checked={r.permissions.includes(item.key)}
                          disabled={!editable || r.name === "super_admin"} onChange={() => toggle(r, item.key)}
                          aria-label={`${item.label} pour ${r.label}`} />
                      </td>
                    ))}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

function ResetPassword({ user, onClose, onDone }: { user: UserRow; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.resetPassword(user.id, password), onDone);
  };
  return (
    <Modal title={tx("Réinitialiser le mot de passe de {0}", [user.full_name])} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <p>{tx("Donnez un mot de passe temporaire à")}{" "}<strong>{user.username}</strong>{" "}{tx(": ses sessions ouvertes sont fermées et il devra le changer à sa prochaine connexion.")}
        </p>
        <Field label={tx("Mot de passe temporaire")}>
          <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} autoComplete="new-password" required autoFocus />
        </Field>
        <p className="muted">{tx("8 caractères minimum, au moins une lettre et un chiffre.")}</p>
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary">{tx("Réinitialiser")}</button>
        </footer>
      </form>
    </Modal>
  );
}

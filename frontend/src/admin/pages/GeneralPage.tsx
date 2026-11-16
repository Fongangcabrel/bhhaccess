import { LangSwitch, tx } from "../../i18n";
import { useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { PasswordForm } from "../ChangePassword";
import { PageHeader } from "../components/ui";

/** Display names of the default roles (the code keeps the technical names). */
const ROLE_LABEL: Record<string, string> = {
  super_admin: tx("Super administrateur"),
  super_user: tx("Super utilisateur"),
  rh: tx("Ressources humaines"),
  agent: tx("Agent"),
};

/** The signed-in person's own settings: account details and password. Open to everyone. */
export function GeneralPage() {
  const { user } = useAuth();
  const [changed, setChanged] = useState(0);

  return (
    <>
      <PageHeader title={tx("Identifiant")} />
      <div className="two-col general">
        <section className="panel">
          <div className="panel-head"><h2>{tx("Mon compte")}</h2></div>
          <dl className="facts">
            <div><dt>{tx("Nom")}</dt><dd>{user?.full_name}</dd></div>
            <div><dt>{tx("Identifiant")}</dt><dd>{user?.username}</dd></div>
            <div><dt>{tx("Rôle")}</dt><dd>{user ? ROLE_LABEL[user.role] ?? user.role : ""}</dd></div>
          </dl>
          <p className="muted">{tx("Votre nom et votre rôle sont gérés par un administrateur.")}</p>
          <div className="lang-row">
            <span>{tx("Langue de l'interface")}</span>
            <LangSwitch reload />
          </div>
          <p className="muted">{tx("Mémorisée sur ce navigateur. Le journal et l'audit restent rédigés en français.")}</p>
        </section>
        <section className="panel">
          <div className="panel-head"><h2>{tx("Mot de passe")}</h2></div>
          {changed > 0 && <p className="note ok-note" role="status">{tx("Mot de passe modifié. Vos autres sessions ont été fermées.")}</p>}
          {/* A new key empties the form after a successful change. */}
          <PasswordForm key={changed} submitLabel={tx("Changer le mot de passe")} autoFocus={false}
            onDone={() => setChanged(changed + 1)} />
        </section>
      </div>
    </>
  );
}

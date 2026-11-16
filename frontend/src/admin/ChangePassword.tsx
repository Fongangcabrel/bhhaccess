import { tx } from "../i18n";
import { type FormEvent, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { PasswordInput } from "../components/PasswordInput";
import { ErrorNote, Field, Modal } from "./components/ui";

const RULES = tx("8 caractères minimum, au moins une lettre et un chiffre, différent de l'identifiant.");

/** Current password + new one typed twice. Used by the forced screen and by "Mon mot de passe". */
export function PasswordForm({ onDone, onCancel, submitLabel, autoFocus = true }: {
  onDone: () => void; onCancel?: () => void; submitLabel: string; autoFocus?: boolean;
}) {
  const { changePassword } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (next !== confirm) return setError(tx("Les deux nouveaux mots de passe ne sont pas identiques."));
    setBusy(true);
    setError(null);
    try {
      await changePassword(current, next);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : tx("Changement impossible"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <Field label={tx("Mot de passe actuel")}>
        <PasswordInput value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" required autoFocus={autoFocus} />
      </Field>
      <Field label={tx("Nouveau mot de passe")}>
        <PasswordInput value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" minLength={8} required />
      </Field>
      <Field label={tx("Confirmer le nouveau mot de passe")}>
        <PasswordInput value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" minLength={8} required />
      </Field>
      <p className="muted">{RULES}{" "}{tx("Vos autres sessions seront fermées.")}</p>
      <ErrorNote message={error} />
      <footer>
        {onCancel && <button type="button" onClick={onCancel}>{tx("Annuler")}</button>}
        <button className="primary" disabled={busy}>{busy ? tx("Enregistrement…") : submitLabel}</button>
      </footer>
    </form>
  );
}

/** Shown instead of the console while the account still has a temporary password. */
export function ForcedPasswordChange() {
  const { user, signOut } = useAuth();
  return (
    <main className="admin forced-password">
      <section className="panel">
        <img src="/logo.png" alt="" className="forced-logo" />
        <h1>{tx("Choisissez votre mot de passe")}</h1>
        <p>{tx("Bonjour {0}. Votre compte utilise un mot de passe temporaire : remplacez-le pour accéder à la console.",
            [user?.full_name])}
        </p>
        <PasswordForm submitLabel={tx("Enregistrer et continuer")} onDone={() => undefined} />
        <button className="link" onClick={signOut}>{tx("Se déconnecter")}</button>
      </section>
    </main>
  );
}

export function ChangePasswordDialog({ onClose }: { onClose: () => void }) {
  const [done, setDone] = useState(false);
  return (
    <Modal title={tx("Changer mon mot de passe")} onClose={onClose}>
      {done ? (
        <div className="form">
          <p>{tx("Mot de passe modifié. Vos autres sessions ont été fermées.")}</p>
          <footer><button className="primary" onClick={onClose}>{tx("Fermer")}</button></footer>
        </div>
      ) : (
        <PasswordForm submitLabel={tx("Changer le mot de passe")} onCancel={onClose} onDone={() => setDone(true)} />
      )}
    </Modal>
  );
}

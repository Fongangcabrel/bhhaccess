import { LangSwitch, tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { PasswordInput } from "../../components/PasswordInput";
import { Shield } from "./Shield";

const UserIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4.2 3.6-7 8-7s8 2.8 8 7" /></svg>
);
const LockIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2.5" /><path d="M8 11V7.5a4 4 0 0 1 7.7-1.5" /></svg>
);

/** Back-office sign-in (administrators). Agents on phones never see this page. */
export function LoginPage() {
  const { signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(username.trim(), password);
    } catch (e) {
      setError(e instanceof Error ? e.message : tx("Connexion impossible"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <LangSwitch reload />
      <div className="login-art" aria-hidden="true"><Shield /></div>
      <form className="login-card" onSubmit={submit}>
        <header>
          <img className="login-logo" src="/logo.png" alt={tx("BHH Access")} />
          <h1>{tx("Connexion")}</h1>
          <p className="sub">{tx("Administration BHH Access")}</p>
        </header>
        <label className="input-icon">
          <UserIcon />
          <input
            aria-label={tx("Identifiant")}
            placeholder={tx("Identifiant")}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label className="input-icon">
          <LockIcon />
          <PasswordInput
            aria-label={tx("Mot de passe")}
            placeholder={tx("Mot de passe")}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p role="alert" className="err">{error}</p>}
        <button className="go" disabled={busy}>{busy ? tx("Connexion…") : tx("Se connecter")}</button>
      </form>
    </main>
  );
}

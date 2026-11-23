import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import type { Device } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { formatDateTime } from "../../lib/format";
import { ActionsMenu, Empty, ErrorNote, Field, Modal, PageHeader } from "../components/ui";
import { DeviceScopeDialog } from "../DeviceScope";
import { useAction, useAsync } from "../useAsync";

const STATUS_LABEL: Record<Device["status"], string> = {
  EN_ATTENTE: tx("En attente d'appairage"),
  APPAIRE: tx("Appairé"),
  REVOQUE: tx("Bloqué"),
};

export function DevicesPage() {
  const { admin, can } = useAuth();
  const devices = useAsync(() => admin.devices(), []);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<{ device: Device; code: string } | null>(null);
  const [renaming, setRenaming] = useState<Device | null>(null);
  const [scoping, setScoping] = useState<Device | null>(null);
  const act = useAction(setError);
  const manage = can("zones.manage");

  const create = (event: FormEvent) => {
    event.preventDefault();
    void (async () => {
      try {
        const result = await admin.createDevice(name.trim());
        setIssued(result);
        setName("");
        void devices.reload();
      } catch (e) {
        setError(e instanceof Error ? e.message : tx("Erreur"));
      }
    })();
  };

  return (
    <>
      <PageHeader title={tx("Téléphones des agents")} />
      <p className="muted">{tx("Les agents ne se connectent pas : chaque téléphone est associé une seule fois avec un code, puis scanne directement. Un téléphone perdu se bloque ici en un clic. Avec la voix, il annonce le résultat (« Entrée autorisée, Jean Mbarga », « Accès refusé… », « Alerte sécurité… ») en plus du bip.")}
      </p>
      <ErrorNote message={error ?? devices.error} />

      {manage && (
        <form className="panel inline-form" onSubmit={create}>
          <input placeholder={tx("Nom du téléphone (ex. Tél. portail principal)")} value={name} onChange={(e) => setName(e.target.value)} required />
          <button className="primary">{tx("Générer un code")}</button>
        </form>
      )}

      <section className="panel flush">
        {devices.data?.length === 0 && <Empty>{tx("Aucun téléphone enregistré.")}</Empty>}
        {!!devices.data?.length && (
          <table className="cards">
            <thead><tr><th>{tx("Nom")}</th><th>{tx("Périmètre")}</th><th>{tx("Poste actuel")}</th><th>{tx("Voix")}</th><th>{tx("État")}</th><th>{tx("Dernière activité")}</th><th /></tr></thead>
            <tbody>
              {devices.data.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>
                    <span className={d.scope_summary && d.scope_summary !== "Tout le site" ? "scope-summary" : "muted"}>
                      {d.scope_summary ?? tx("Tout le site")}
                    </span>
                  </td>
                  <td>
                    {d.current_post
                      ? <>{d.current_post}{d.checkpoint_since && <><br /><span className="muted">{tx("depuis {0}", [formatDateTime(d.checkpoint_since)])}</span></>}</>
                      : <span className="muted">–</span>}
                  </td>
                  <td>
                    <VoiceSwitch on={d.voice_enabled !== false} disabled={!manage} name={d.name}
                      onChange={(on) => void act(() => admin.setDeviceVoice(d.id, on), () => void devices.reload())} />
                  </td>
                  <td><span className={`status ${d.status}`}>{STATUS_LABEL[d.status]}</span></td>
                  <td>{d.last_seen_at ? formatDateTime(d.last_seen_at) : "–"}</td>
                  <td className="right">
                    {manage && (
                      <ActionsMenu label={d.name} actions={[
                        { label: d.status === "APPAIRE" ? tx("Réassocier (nouveau code)") : tx("Nouveau code"),
                          onClick: () => void act(async () => setIssued(await admin.newDeviceCode(d.id)), () => void devices.reload()) },
                        { label: tx("Définir le périmètre"), onClick: () => setScoping(d) },
                        { label: tx("Renommer"), onClick: () => setRenaming(d) },
                        ...(d.status !== "REVOQUE" ? [{ label: tx("Bloquer (effet immédiat)"), danger: true,
                          onClick: () => window.confirm(tx("Bloquer « {0} » ? Il ne pourra plus scanner immédiatement.", [d.name])) && void act(() => admin.revokeDevice(d.id), () => void devices.reload()) }] : []),
                        { label: tx("Supprimer"), danger: true, hint: tx("Possible seulement si le téléphone n'a jamais scanné ; sinon bloquez-le"),
                          onClick: () => window.confirm(tx("Supprimer « {0} » ?", [d.name])) && void act(() => admin.deleteDevice(d.id), () => void devices.reload()) },
                      ]} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {scoping && (
        <DeviceScopeDialog device={scoping} onClose={() => setScoping(null)}
          onDone={() => { setScoping(null); void devices.reload(); }} />
      )}
      {renaming && (
        <RenameDevice device={renaming} onClose={() => setRenaming(null)}
          onDone={() => { setRenaming(null); void devices.reload(); }} />
      )}

      {issued && (
        <Modal title={tx("Appairer « {0} »", [issued.device.name])} onClose={() => setIssued(null)}>
          <div className="code-box">
            <span className="muted">{tx("Code à saisir sur le téléphone (valable 15 minutes, usage unique)")}</span>
            <strong>{issued.code.slice(0, 4)}-{issued.code.slice(4)}</strong>
            <p className="muted">{tx("Ou ouvrir ce lien sur le téléphone :")}</p>
            <code>{`${window.location.origin}/pair/${issued.code}`}</code>
          </div>
          <div className="form"><footer><button className="primary" onClick={() => setIssued(null)}>{tx("Terminé")}</button></footer></div>
        </Modal>
      )}
    </>
  );
}

function RenameDevice({ device, onClose, onDone }: { device: Device; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [name, setName] = useState(device.name);
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.renameDevice(device.id, name.trim()), onDone);
  };
  return (
    <Modal title={tx("Renommer le téléphone")} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label={tx("Nom")}><input value={name} onChange={(e) => setName(e.target.value)} required autoFocus /></Field>
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary">{tx("Enregistrer")}</button>
        </footer>
      </form>
    </Modal>
  );
}

/** Voice on / off for one phone (the beep always stays). */
function VoiceSwitch({ on, disabled, name, onChange }: {
  on: boolean; disabled: boolean; name: string; onChange: (on: boolean) => void;
}) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={tx("Voix de « {0} »", [name])} disabled={disabled}
      className={`voice-switch${on ? " on" : ""}`} onClick={() => onChange(!on)}>
      <span className="knob" aria-hidden="true" />
      {on ? tx("Activée") : tx("Coupée")}
    </button>
  );
}

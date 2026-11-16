import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { AccessZone, Badge, Employee, RevocationReason } from "../../api/types";
import { RestrictionsDialog } from "../AccessRestrictions";
import { useAuth } from "../../auth/AuthContext";
import { downloadBlob, formatDateTime, openPdf } from "../../lib/format";
import { Empty, ErrorNote, Field, Modal, PageHeader } from "../components/ui";
import { Silhouette } from "../../components/Silhouette";
import { EmployeeForm, STATUS_LABEL } from "./EmployeesPage";
import { useAction, useAsync } from "../useAsync";

export function EmployeeDetailPage() {
  const id = Number(useParams().id);
  const { admin, can } = useAuth();
  const employee = useAsync(() => admin.employee(id), [id]);
  const badges = useAsync(() => admin.badges(id), [id]);
  const access = useAsync(() => admin.access(id), [id]);
  const [ticked, setTicked] = useState<Set<number> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [qr, setQr] = useState<{ badge: Badge; url: string } | null>(null);
  const [dialog, setDialog] = useState<"edit" | "archive" | null>(null);
  const [revoking, setRevoking] = useState<Badge | null>(null);
  const [restricting, setRestricting] = useState<AccessZone | null>(null);
  const act = useAction(setError);

  const e = employee.data;
  if (employee.error) return <ErrorNote message={employee.error} />;
  if (!e) return <p className="muted">{tx("Chargement…")}</p>;

  const archived = e.status === "ARCHIVE";
  const activeBadge = badges.data?.find((b) => b.status === "ACTIF");
  const reloadAll = () => { void employee.reload(); void badges.reload(); };
  const suspend = () =>
    window.confirm(tx("Suspendre cet employé ? Son badge sera refusé à l'entrée (la sortie reste possible).")) &&
    act(() => admin.setEmployeeStatus(id, "SUSPENDU"), reloadAll);
  const reactivate = () => act(() => admin.setEmployeeStatus(id, "ACTIF"), reloadAll);
  const restore = () =>
    window.confirm(tx("Restaurer cet employé ? Sa fiche et ses zones reviennent ; il faudra émettre un nouveau badge.")) &&
    act(() => admin.restoreEmployee(id), reloadAll);
  const issue = () =>
    (!activeBadge || window.confirm(tx("Réémettre ? Le badge v{0} sera révoqué (motif « Remplacement ») et son QR ne marchera plus.", [activeBadge.version]))) &&
    act(() => admin.issueBadge(id), () => void badges.reload());
  const showQr = (badge: Badge) =>
    act(async () => setQr({ badge, url: URL.createObjectURL(await admin.badgeQr(badge.id)) }));
  // The checkboxes start from what the server says; "ticked" holds unsaved changes.
  const granted = new Set(access.data?.flatMap((u) => u.zones.filter((z) => z.granted).map((z) => z.id)));
  const current = ticked ?? granted;
  const dirty = ticked !== null && (ticked.size !== granted.size || [...ticked].some((z) => !granted.has(z)));
  const toggle = (zoneId: number) => {
    const next = new Set(current);
    if (next.has(zoneId)) next.delete(zoneId); else next.add(zoneId);
    setTicked(next);
  };
  const unitStatus = (zones: { id: number }[]) => (zones.some((z) => current.has(z.id)) ? "ACCES" : "REFUSE");
  const saveAccess = () => act(() => admin.setAccess(id, [...current]), () => { setTicked(null); void access.reload(); });

  return (
    <>
      <p><Link to="/admin/employes">{tx("← Employés")}</Link></p>
      <PageHeader title={`${e.first_name} ${e.last_name}`}>
        <span className={`status ${e.status}`}>{STATUS_LABEL[e.status]}</span>
        {!archived && can("employees.edit") && <button onClick={() => setDialog("edit")}>{tx("Modifier")}</button>}
        {e.status === "ACTIF" && can("employees.edit") && <button onClick={suspend}>{tx("Suspendre")}</button>}
        {e.status === "SUSPENDU" && can("employees.edit") && <button onClick={reactivate}>{tx("Réactiver")}</button>}
        {!archived && can("employees.archive") && <button className="danger" onClick={() => setDialog("archive")}>{tx("Archiver")}</button>}
        {archived && can("employees.archive") && <button className="primary" onClick={restore}>{tx("Restaurer")}</button>}
      </PageHeader>
      <ErrorNote message={error} />
      {archived && (
        <p className="note warn-note">
          <strong>{tx("Employé archivé")}</strong>
          {e.archived_at && <>{" "}{tx("le {0}", [formatDateTime(e.archived_at)])}</>}
          {e.archive_reason && <>{" "}{tx("· motif :")}{" "}{e.archive_reason}</>}.{" "}{tx("Son QR affiche « QR non reconnu » aux agents. Pour le réintégrer : « Restaurer », puis émettre un nouveau badge.")}
        </p>
      )}

      <section className="panel identity">
        <PhotoBlock employee={e} canEdit={can("employees.edit") && !archived}
          onError={setError} onChanged={() => void employee.reload()} />
        <dl className="facts">
          <div><dt>{tx("Matricule")}</dt><dd>{e.matricule}</dd></div>
          <div><dt>{tx("Fonction")}</dt><dd>{e.job_title ?? "–"}</dd></div>
          <div><dt>{tx("Entité")}</dt><dd>{e.entity_name ?? "–"}</dd></div>
          <div><dt>{tx("Département")}</dt><dd>{e.department_name ?? "–"}</dd></div>
        </dl>
      </section>

      <div className="two-col">
        <section className="panel">
          <div className="panel-head">
            <h2>{tx("Badges")}</h2>
            {can("badges.issue") && !archived && (
              <button className="primary small" onClick={issue} disabled={e.status !== "ACTIF"}
                title={e.status !== "ACTIF" ? tx("Réactivez l'employé pour lui émettre un badge") : undefined}>
                {activeBadge ? tx("Réémettre") : tx("Émettre un badge")}
              </button>
            )}
          </div>
          {e.status === "SUSPENDU" && can("badges.issue") && (
            <p className="muted">{tx("Employé suspendu : réactivez-le pour lui émettre un badge.")}</p>
          )}
          {badges.data?.length === 0 && <Empty>{tx("Aucun badge émis.")}</Empty>}
          {!!badges.data?.length && (
            <table className="cards">
              <thead><tr><th>{tx("Version")}</th><th>{tx("Émis le")}</th><th>{tx("Statut")}</th><th>{tx("Motif")}</th><th /></tr></thead>
              <tbody>
                {badges.data.map((b) => (
                  <tr key={b.id}>
                    <td>v{b.version}</td>
                    <td>{formatDateTime(b.issued_at)}</td>
                    <td><span className={`status ${b.status}`}>{b.status === "ACTIF" ? tx("actif") : tx("révoqué")}</span></td>
                    <td>
                      {b.status === "REVOQUE" ? (
                        <span title={b.revoked_note ?? undefined}>
                          {b.revoked_reason ? REVOCATION_LABEL[b.revoked_reason] : "–"}
                          {b.revoked_at && <span className="muted"> · {formatDateTime(b.revoked_at)}</span>}
                          {b.revoked_note && <span className="muted block">{b.revoked_note}</span>}
                        </span>
                      ) : "–"}
                    </td>
                    <td className="right">
                      {b.status === "ACTIF" && can("badges.issue") && <button className="small" onClick={() => showQr(b)}>{tx("Voir le QR")}</button>}{" "}
                      {b.status === "ACTIF" && can("badges.revoke") && (
                        <button className="small danger" onClick={() => setRevoking(b)}>{tx("Révoquer")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>{tx("Accès par unité")}</h2>
            {can("authorizations.manage") && (
              <button className="primary small" disabled={!dirty} onClick={saveAccess}>{tx("Enregistrer")}</button>
            )}
          </div>
          {access.data?.length === 0 && <Empty>{tx("Aucune unité n'est configurée.")}</Empty>}
          {access.data?.map((unit) => {
            const status = unitStatus(unit.zones);
            return (
              <div className="unit" key={unit.unit_id}>
                <header>
                  <h3>{unit.unit_name}</h3>
                  <span className={`status ${status}`}>{status === "ACCES" ? tx("Accès") : tx("Refusé")}</span>
                </header>
                <div className="body">
                  {unit.zones.length === 0 && <Empty>{tx("Cette unité n'a pas encore de zone.")}</Empty>}
                  <div className="zone-pick">
                    {unit.zones.map((zone) => (
                      <div className="zone-row" key={zone.id}>
                        <label>
                          <input
                            type="checkbox"
                            checked={current.has(zone.id)}
                            disabled={!can("authorizations.manage")}
                            onChange={() => toggle(zone.id)}
                          />
                          {zone.name}
                        </label>
                        {zone.granted && current.has(zone.id) && (
                          <span className="restrict">
                            {zone.restrictions
                              ? <span className={`summary${zone.usable_now === false ? " off" : ""}`}
                                  title={zone.usable_now === false ? tx("En dehors de ses dates ou horaires en ce moment") : undefined}>
                                  {zone.restrictions}
                                </span>
                              : <span className="muted">{tx("permanent, 24 h/24")}</span>}
                            {can("authorizations.manage") && !dirty && (
                              <button className="link" onClick={() => setRestricting(zone)}>
                                {zone.restrictions ? tx("Modifier") : tx("Limiter…")}
                              </button>
                            )}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </section>
      </div>

      {dialog === "edit" && (
        <EmployeeForm employee={e} onClose={() => setDialog(null)} onDone={() => { setDialog(null); void employee.reload(); }} />
      )}
      {restricting && (
        <RestrictionsDialog employeeId={id} zone={restricting} onClose={() => setRestricting(null)}
          onDone={() => { setRestricting(null); void access.reload(); }} />
      )}
      {revoking && (
        <RevokeDialog badge={revoking} matricule={e.matricule} onClose={() => setRevoking(null)}
          onDone={() => { setRevoking(null); void badges.reload(); }} />
      )}
      {dialog === "archive" && (
        <ArchiveDialog employee={e} onClose={() => setDialog(null)} onDone={() => { setDialog(null); reloadAll(); }} />
      )}

      {qr && (
        <Modal title={tx("Badge v{0} · {1}", [qr.badge.version, e.matricule])} onClose={() => { URL.revokeObjectURL(qr.url); setQr(null); }}>
          <div className="qr-box">
            <img src={qr.url} alt={tx("QR du badge {0}", [e.matricule])} />
            <p className="muted">{tx("Le badge imprimable porte le QR (logo au centre) et le matricule, à taille réelle : imprimez à 100 %, découpez, plastifiez, puis testez la lecture.")}
            </p>
            <div className="inline">
              <button className="primary" onClick={() => act(async () => openPdf(await admin.badgePdf(qr.badge.id), `badge-${e.matricule}.pdf`))}>{tx("Imprimer le badge (PDF)")}
              </button>
              <button onClick={async () => downloadBlob(await admin.badgeQr(qr.badge.id), `badge-${e.matricule}.png`)}>{tx("Image du QR (PNG)")}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

const REVOCATION_LABEL: Record<RevocationReason, string> = {
  PERTE: tx("Perte"),
  VOL: tx("Vol"),
  DEPART: tx("Départ"),
  REMPLACEMENT: tx("Remplacement"),
  AUTRE: tx("Autre"),
};

const REVOKE_CHOICES: RevocationReason[] = ["PERTE", "VOL", "DEPART", "AUTRE"];

/** Revoke with a reason (SRS FR-52). The QR stops working at once and is never reactivated. */
function RevokeDialog({ badge, matricule, onClose, onDone }: {
  badge: Badge; matricule: string; onClose: () => void; onDone: () => void;
}) {
  const { admin } = useAuth();
  const [reason, setReason] = useState<RevocationReason>("PERTE");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const needsNote = reason === "AUTRE";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.revokeBadge(badge.id, reason, note.trim()), onDone);
  };

  return (
    <Modal title={tx("Révoquer le badge v{0} · {1}", [badge.version, matricule])} onClose={onClose}>
      <form onSubmit={submit} className="form">
        <p>{tx("Le QR de ce badge")}{" "}<strong>{tx("ne donnera plus accès dès maintenant")}</strong>.{" "}{tx("L'agent verra « Badge révoqué » avec la photo et l'identité : il peut alors retenir la personne. Un badge révoqué n'est jamais réactivé : pour redonner l'accès, émettez un nouveau badge.")}</p>
        <fieldset className="reasons">
          <legend>{tx("Motif")}</legend>
          {REVOKE_CHOICES.map((r) => (
            <label key={r} className="reason">
              <input type="radio" name="reason" value={r} checked={reason === r} onChange={() => setReason(r)} />
              {REVOCATION_LABEL[r]}
            </label>
          ))}
        </fieldset>
        <Field label={needsNote ? tx("Précision (obligatoire)") : tx("Précision (facultatif)")}>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300}
            placeholder={needsNote ? tx("Expliquez le motif") : tx("Lieu, date, n° de déclaration…")} required={needsNote} />
        </Field>
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="danger" disabled={needsNote && !note.trim()}>{tx("Révoquer le badge")}</button>
        </footer>
      </form>
    </Modal>
  );
}

function ArchiveDialog({ employee, onClose, onDone }: { employee: Employee; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.archiveEmployee(employee.id, reason.trim()), onDone);
  };

  return (
    <Modal title={tx("Archiver {0} {1}", [employee.first_name, employee.last_name])} onClose={onClose}>
      <form onSubmit={submit} className="form">
        <p>{tx("L'employé quitte les listes et")}{" "}<strong>{tx("ses badges sont révoqués immédiatement")}</strong>{" "}{tx(": son QR affichera « QR non reconnu ». Son historique est conservé et il peut être restauré.")}</p>
        <Field label={tx("Motif (obligatoire)")}>
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={tx("Départ, fin de contrat…")} required minLength={3} autoFocus />
        </Field>
        <ErrorNote message={error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="danger" disabled={reason.trim().length < 3}>{tx("Archiver")}</button>
        </footer>
      </form>
    </Modal>
  );
}

const PHOTO_MAX_BYTES = 2 * 1024 * 1024;

/** Portrait photo with change / remove; the server crops and cleans it (no EXIF kept). */
function PhotoBlock({ employee, canEdit, onError, onChanged }: {
  employee: Employee; canEdit: boolean; onError: (message: string | null) => void; onChanged: () => void;
}) {
  const { admin } = useAuth();
  const [busy, setBusy] = useState(false);
  const act = useAction(onError);
  const send = (file: File | undefined) => {
    if (!file) return;
    if (!["image/jpeg", "image/png"].includes(file.type)) return onError(tx("Format refusé : JPEG ou PNG uniquement."));
    if (file.size > PHOTO_MAX_BYTES) return onError(tx("Photo trop lourde : 2 Mo maximum."));
    setBusy(true);
    void act(() => admin.uploadPhoto(employee.id, file), onChanged).finally(() => setBusy(false));
  };
  const remove = () =>
    window.confirm(tx("Retirer la photo ? L'agent verra « Photo absente » au scan.")) &&
    act(() => admin.deletePhoto(employee.id), onChanged);

  return (
    <figure className="photo-block">
      {employee.photo_url ? (
        <img src={employee.photo_url} alt={tx("Photo de {0} {1}", [employee.first_name, employee.last_name])} />
      ) : (
        <div className="photo-absent" role="img" aria-label={tx("Photo absente")}><Silhouette /><span>{tx("Photo absente")}</span></div>
      )}
      {canEdit && (
        <figcaption>
          <label className={`button small${busy ? " disabled" : ""}`}>
            {busy ? tx("Envoi…") : employee.has_photo ? tx("Changer") : tx("Ajouter une photo")}
            <input type="file" accept="image/jpeg,image/png" hidden disabled={busy}
              onChange={(event) => { send(event.target.files?.[0]); event.target.value = ""; }} />
          </label>
          {employee.has_photo && <button className="small" onClick={remove} disabled={busy}>{tx("Retirer")}</button>}
        </figcaption>
      )}
    </figure>
  );
}

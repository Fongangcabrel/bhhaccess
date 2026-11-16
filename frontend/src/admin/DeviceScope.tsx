import { tx } from "../i18n";
import { useState } from "react";
import type { Device, DeviceScopeIds } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorNote, Modal } from "./components/ui";
import { useAction, useAsync } from "./useAsync";

/**
 * What a phone covers (tâche 41): whole units, whole zones or single posts. A ticked unit or
 * zone includes what is inside, also what is created there later. Nothing ticked = whole site.
 */
export function DeviceScopeDialog({ device, onClose, onDone }: { device: Device; onClose: () => void; onDone: () => void }) {
  const { admin } = useAuth();
  const units = useAsync(() => admin.units(), []);
  const posts = useAsync(() => admin.checkpoints(), []);
  const initial = device.scope_ids ?? { unit_ids: [], zone_ids: [], checkpoint_ids: [] };
  const [unitIds, setUnitIds] = useState(new Set(initial.unit_ids));
  const [zoneIds, setZoneIds] = useState(new Set(initial.zone_ids));
  const [postIds, setPostIds] = useState(new Set(initial.checkpoint_ids));
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);

  const flip = (set: Set<number>, apply: (s: Set<number>) => void, id: number) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id); else next.add(id);
    apply(next);
  };
  const nothing = unitIds.size + zoneIds.size + postIds.size === 0;
  const save = () => {
    const body: DeviceScopeIds = { unit_ids: [...unitIds], zone_ids: [...zoneIds], checkpoint_ids: [...postIds] };
    void act(() => admin.setDeviceScope(device.id, body), onDone);
  };

  return (
    <Modal title={tx("Périmètre · {0}", [device.name])} onClose={onClose}>
      <div className="form scope">
        <p className="muted">{tx("Cochez ce que ce téléphone couvre : il ne proposera que ces postes à l'agent et refusera de scanner ailleurs. Une unité ou une zone cochée inclut aussi les postes ajoutés plus tard. Rien de coché : tout le site.")}
        </p>
        {units.data?.map((unit) => {
          const unitOn = unitIds.has(unit.id);
          return (
            <fieldset key={unit.id} className="scope-unit">
              <legend>
                <label className="check">
                  <input type="checkbox" checked={unitOn} onChange={() => flip(unitIds, setUnitIds, unit.id)} />
                  {unit.name} <span className="muted">{tx("(toute l'unité)")}</span>
                </label>
              </legend>
              {unit.zones.length === 0 && <p className="muted">{tx("Aucune zone.")}</p>}
              {unit.zones.map((zone) => {
                const zoneOn = unitOn || zoneIds.has(zone.id);
                const zonePosts = (posts.data ?? []).filter((p) => p.zone_id === zone.id);
                return (
                  <div key={zone.id} className="scope-zone">
                    <label className="check">
                      <input type="checkbox" checked={zoneOn} disabled={unitOn} onChange={() => flip(zoneIds, setZoneIds, zone.id)} />
                      <strong>{zone.name}</strong> <span className="muted">{tx("(toute la zone)")}</span>
                    </label>
                    <div className="scope-posts">
                      {zonePosts.length === 0 && <span className="muted">{tx("aucun poste")}</span>}
                      {zonePosts.map((post) => (
                        <label className="check" key={post.id}>
                          <input type="checkbox" checked={zoneOn || postIds.has(post.id)} disabled={zoneOn}
                            onChange={() => flip(postIds, setPostIds, post.id)} />
                          {post.name} <span className="muted">· {post.direction === "ENTREE" ? tx("entrée") : "sortie"}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}
            </fieldset>
          );
        })}
        {nothing && <p className="note warn-note">{tx("Rien de coché : ce téléphone verra tous les postes du site.")}</p>}
        <ErrorNote message={error ?? units.error} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary" onClick={save}>{tx("Enregistrer")}</button>
        </footer>
      </div>
    </Modal>
  );
}

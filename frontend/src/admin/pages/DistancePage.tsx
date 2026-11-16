import { tx } from "../../i18n";
import { type FormEvent, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { ErrorNote, PageHeader } from "../components/ui";
import { useAction, useAsync } from "../useAsync";

/** Configure the minimum allowed travel time between two control posts. */
export function DistancePage() {
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <PageHeader title={tx("Réglage de distance")} />
      <ErrorNote message={error} />
      <TravelTimes onError={setError} />
    </>
  );
}

function TravelTimes({ onError }: { onError: (message: string | null) => void }) {
  const { admin, can } = useAuth();
  const rows = useAsync(() => admin.travelTimes(), []);
  const posts = useAsync(() => admin.checkpoints(), []);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [minutes, setMinutes] = useState("5");
  const act = useAction(onError);
  const manage = can("zones.manage");
  const label = (c: { name: string; zone_name: string; unit_name: string }) =>
    `${c.name} · ${c.zone_name} (${c.unit_name})`;
  const save = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.setTravelTime(Number(a), Number(b), Number(minutes)), () => {
      setA("");
      setB("");
      void rows.reload();
    });
  };

  return (
    <section className="panel travel">
      <div className="panel-head"><h2>{tx("Temps de trajet minimum entre postes")}</h2></div>
      <p className="muted">
        {tx("Si le même badge est scanné à deux postes plus vite que ce temps, une alerte « Utilisation simultanée » est créée. Par défaut : 10 minutes entre deux unités différentes, aucun contrôle à l'intérieur d'une même unité. Mettez 0 pour ne jamais contrôler une paire.")}
      </p>
      {rows.data?.length === 0 && <p className="muted">{tx("Aucun temps réglé : les valeurs par défaut s'appliquent.")}</p>}
      {!!rows.data?.length && (
        <ul className="travel-list">
          {rows.data.map((travelTime) => (
            <li key={travelTime.id}>
              <span>{travelTime.checkpoint_a_name} <span aria-hidden="true">↔</span> {travelTime.checkpoint_b_name}</span>
              <strong>{travelTime.min_seconds === 0 ? tx("pas de contrôle") : `${Math.round(travelTime.min_seconds / 6) / 10} min`}</strong>
              {manage && (
                <button className="small" onClick={() =>
                  void act(() => admin.deleteTravelTime(travelTime.id), () => void rows.reload())
                }>
                  {tx("Retirer")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {manage && (
        <form className="travel-form" onSubmit={save}>
          <select value={a} onChange={(e) => setA(e.target.value)} required aria-label={tx("Premier poste")}>
            <option value="">{tx("Poste…")}</option>
            {posts.data?.map((checkpoint) => (
              <option key={checkpoint.id} value={checkpoint.id}>{label(checkpoint)}</option>
            ))}
          </select>
          <select value={b} onChange={(e) => setB(e.target.value)} required aria-label={tx("Second poste")}>
            <option value="">{tx("Autre poste…")}</option>
            {posts.data?.filter((checkpoint) => String(checkpoint.id) !== a).map((checkpoint) => (
              <option key={checkpoint.id} value={checkpoint.id}>{label(checkpoint)}</option>
            ))}
          </select>
          <label className="inline-label">{tx("Minutes")}
            <input type="number" min={0} max={1440} step={0.5} value={minutes}
              onChange={(e) => setMinutes(e.target.value)} required />
          </label>
          <button className="primary">{tx("Enregistrer")}</button>
        </form>
      )}
    </section>
  );
}

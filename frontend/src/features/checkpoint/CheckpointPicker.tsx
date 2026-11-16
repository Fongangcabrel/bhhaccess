import { LangSwitch, useT } from "../../i18n";
import { useEffect, useMemo, useState } from "react";
import type { Checkpoint } from "../../api/types";
import { useDevice } from "../../device/DeviceContext";

interface Props {
  onSelect: (checkpoint: Checkpoint) => void;
}

/** Posts grouped by unit, then zone. Shows who is posted where (when the super user recorded it). */
export function CheckpointPicker({ onSelect }: Props) {
  const { api, deviceName, unpair } = useDevice();
  const { t } = useT();
  const [checkpoints, setCheckpoints] = useState<Checkpoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.checkpoints().then(setCheckpoints).catch((e: Error) => setError(e.message));
  }, [api]);

  const grouped = useMemo(() => {
    const units = new Map<string, Map<string, Checkpoint[]>>();
    for (const c of checkpoints ?? []) {
      const zones = units.get(c.unit_name) ?? new Map<string, Checkpoint[]>();
      zones.set(c.zone_name, [...(zones.get(c.zone_name) ?? []), c]);
      units.set(c.unit_name, zones);
    }
    return [...units.entries()];
  }, [checkpoints]);

  return (
    <main className="page">
      <div className="brandbar">
        <img src="/logo.png" alt="" />
        <div>
          <strong>{t("picker.title")}</strong>
          <span className="muted">{deviceName ?? t("picker.thisPhone")}</span>
        </div>
        <LangSwitch />
      </div>
      <p className="muted">{t("picker.intro")}</p>
      {error && <p role="alert" className="error">{error}</p>}
      {grouped.map(([unit, zones]) => (
        <section key={unit}>
          <h2>{unit}</h2>
          {[...zones.entries()].map(([zone, items]) => (
            <div key={zone} className="stack" style={{ marginBottom: ".8rem" }}>
              {items.map((c) => (
                <button key={c.id} className="choice" onClick={() => onSelect(c)}>
                  <span>
                    {c.name}
                    <small>{zone}{c.agent_name ? ` · ${c.agent_name}` : ""}</small>
                  </span>
                  <span className={`dir ${c.direction === "ENTREE" ? "in" : "out"}`}>
                    {c.direction === "ENTREE" ? t("dir.in") : t("dir.out")}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </section>
      ))}
      {checkpoints?.length === 0 && <p className="muted">{t("picker.empty")}</p>}
      <button className="link" onClick={() => window.confirm(t("picker.unpairConfirm")) && unpair()}>
        {t("picker.unpair")}
      </button>
    </main>
  );
}

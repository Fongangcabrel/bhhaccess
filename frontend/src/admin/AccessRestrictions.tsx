import { tx } from "../i18n";
import { type FormEvent, useState } from "react";
import type { AccessZone, Schedule } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { endOfDayIso, startOfDayIso } from "../lib/format";
import { ErrorNote, Field, Modal } from "./components/ui";
import { useAction } from "./useAsync";

// Letter on the day button = first letter of the day's name, in the language shown.
const DAYS: [number, string, string][] = (
  [[1, tx("lundi")], [2, tx("mardi")], [3, tx("mercredi")], [4, tx("jeudi")], [5, tx("vendredi")],
    [6, tx("samedi")], [7, tx("dimanche")]] as [number, string][]
).map(([n, name]) => [n, name.charAt(0).toUpperCase(), name]);
const NEW_SLOT: Schedule = { weekdays: [1, 2, 3, 4, 5], start: "07:00", end: "18:00" };

/** "2026-11-30T22:59:59Z" -> "2026-11-30" in Douala time (UTC+1, no daylight saving). */
const toLocalDate = (iso: string | null | undefined): string => {
  if (!iso) return "";
  const local = new Date(new Date(iso).getTime() + 60 * 60 * 1000);
  return local.toISOString().slice(0, 10);
};
const hhmm = (value: string) => value.slice(0, 5);

/**
 * Dates (temporary access) and weekly time slots of one ticked zone (SRS FR-43, PRD F11).
 * Nothing filled in = permanent access, 24 h / 24. Exits are never blocked.
 */
export function RestrictionsDialog({ employeeId, zone, onClose, onDone }: {
  employeeId: number; zone: AccessZone; onClose: () => void; onDone: () => void;
}) {
  const { admin } = useAuth();
  const [from, setFrom] = useState(toLocalDate(zone.valid_from));
  const [until, setUntil] = useState(toLocalDate(zone.valid_until));
  const [slots, setSlots] = useState<Schedule[]>(
    (zone.schedules ?? []).map((s) => ({ ...s, start: hhmm(s.start), end: hhmm(s.end) })));
  const [error, setError] = useState<string | null>(null);
  const act = useAction(setError);

  const update = (index: number, change: Partial<Schedule>) =>
    setSlots(slots.map((s, i) => (i === index ? { ...s, ...change } : s)));
  const toggleDay = (index: number, day: number) => {
    const days = slots[index].weekdays;
    update(index, { weekdays: days.includes(day) ? days.filter((d) => d !== day) : [...days, day].sort() });
  };
  const invalid = slots.some((s) => s.weekdays.length === 0) || (!!from && !!until && until < from);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void act(() => admin.setRestrictions(employeeId, zone.id, {
      valid_from: from ? startOfDayIso(from) : null,
      valid_until: until ? endOfDayIso(until) : null,
      schedules: slots,
    }), onDone);
  };

  return (
    <Modal title={tx("Dates et horaires · {0}", [zone.name])} onClose={onClose}>
      <form className="form restrictions" onSubmit={submit}>
        <p className="muted">{tx("Laissez tout vide pour un accès permanent, 24 h/24. En dehors des dates ou des horaires, l'entrée est refusée avec le motif à l'écran de l'agent ;")}{" "}<strong>{tx("la sortie n'est jamais bloquée")}</strong>.
        </p>
        <fieldset>
          <legend>{tx("Accès temporaire")}</legend>
          <div className="inline">
            <Field label={tx("À partir du")}><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
            <Field label={tx("Jusqu'au (inclus)")}><input type="date" value={until} min={from || undefined} onChange={(e) => setUntil(e.target.value)} /></Field>
          </div>
        </fieldset>
        <fieldset>
          <legend>{tx("Horaires autorisés")}</legend>
          {slots.length === 0 && <p className="muted">{tx("Aucune plage : accès à toute heure.")}</p>}
          {slots.map((slot, index) => (
            <div className="slot" key={index}>
              <div className="days" role="group" aria-label={tx("Jours de la plage {0}", [index + 1])}>
                {DAYS.map(([day, letter, name]) => (
                  <button type="button" key={day} title={name} aria-label={name}
                    aria-pressed={slot.weekdays.includes(day)} className={slot.weekdays.includes(day) ? "on" : ""}
                    onClick={() => toggleDay(index, day)}>
                    {letter}
                  </button>
                ))}
              </div>
              <label className="time">{tx("De")}<input type="time" value={slot.start} required onChange={(e) => update(index, { start: e.target.value })} /></label>
              <label className="time">{tx("à")}<input type="time" value={slot.end} required onChange={(e) => update(index, { end: e.target.value })} /></label>
              <button type="button" className="small" aria-label={tx("Retirer la plage {0}", [index + 1])}
                onClick={() => setSlots(slots.filter((_, i) => i !== index))}>{tx("Retirer")}</button>
              {slot.end < slot.start && <small className="muted night">{tx("Plage de nuit : se termine le lendemain matin.")}</small>}
              {slot.end === slot.start && <small className="muted night">{tx("Début = fin : toute la journée.")}</small>}
            </div>
          ))}
          {slots.length < 10 && (
            <button type="button" className="small" onClick={() => setSlots([...slots, { ...NEW_SLOT }])}>{tx("+ Ajouter une plage")}</button>
          )}
        </fieldset>
        <ErrorNote message={error ?? (invalid ? tx("Chaque plage doit avoir au moins un jour, et la fin doit suivre le début.") : null)} />
        <footer>
          <button type="button" onClick={onClose}>{tx("Annuler")}</button>
          <button className="primary" disabled={invalid}>{tx("Enregistrer")}</button>
        </footer>
      </form>
    </Modal>
  );
}

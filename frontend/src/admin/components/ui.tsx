import { tx } from "../../i18n";
import { type ReactNode, useEffect, useRef, useState } from "react";
import type { Verdict } from "../../api/types";
import { describeVerdict } from "../../lib/verdicts";

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" role="dialog" aria-label={title} onMouseDown={(e) => e.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <button className="icon" onClick={onClose} aria-label={tx("Fermer")}>×</button>
        </header>
        {children}
      </div>
    </div>
  );
}

export const ErrorNote = ({ message }: { message: string | null }) =>
  message ? <p role="alert" className="note error-note">{message}</p> : null;

export const Empty = ({ children }: { children: ReactNode }) => <p className="empty">{children}</p>;

export function VerdictPill({ verdict }: { verdict: Verdict }) {
  const view = describeVerdict(verdict);
  return <span className={`vpill ${view.tone}`}>{view.short}</span>;
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="page-head">
      <h1>{title}</h1>
      <div className="actions">{children}</div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export interface MenuAction {
  label: string;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
  /** Why the action is disabled, shown as a tooltip. */
  hint?: string;
}

/** "⋯" button opening a short list of actions: keeps rows readable, on desktop and on phones. */
export function ActionsMenu({ label, actions }: { label: string; actions: MenuAction[] }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !root.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);
  return (
    <div className="menu" ref={root}>
      <button type="button" className="small kebab" aria-haspopup="menu" aria-expanded={open}
        aria-label={tx("Actions : {0}", [label])} onClick={() => setOpen(!open)}>
        ⋯
      </button>
      {open && (
        <div className="menu-list" role="menu">
          {actions.map((action) => (
            <button key={action.label} type="button" role="menuitem" disabled={action.disabled} title={action.hint}
              className={action.danger ? "danger" : undefined}
              onClick={() => { setOpen(false); action.onClick(); }}>
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

import { tx } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { getLang } from "../lib/lang";
import { safeStorage } from "../lib/storage";
import { alertAnnouncement, speak } from "../lib/voice";
import { useCardLabels } from "./useCardLabels";

type MenuItem = { to: string; label: string; right: string | null };

/** The menu, by section. A section without any item allowed for this person is hidden. */
export const MENU_SECTIONS: { title: string | null; items: MenuItem[] }[] = [
  { title: null, items: [{ to: "/admin/dashboard", label: tx("Tableau de bord"), right: "logs.view" }] },
  {
    title: tx("Paramétrage"),
    items: [
      { to: "/admin/employes", label: tx("Employés"), right: "employees.view" },
      { to: "/admin/organisation", label: tx("Entités et départements"), right: "employees.view" },
      { to: "/admin/zones", label: tx("Unités et zones"), right: "zones.view" },
      { to: "/admin/distance-conforme", label: tx("Réglage de distance"), right: "reports.view" },
      { to: "/admin/agents", label: tx("Agents"), right: "zones.view" },
      { to: "/admin/telephones", label: tx("Téléphones"), right: "zones.view" },
      { to: "/admin/utilisateurs", label: tx("Utilisateurs"), right: "users.manage" },
    ],
  },
  {
    title: tx("Rapport"),
    items: [
      { to: "/admin/journal", label: tx("Journal"), right: "logs.view" },
      { to: "/admin/alertes", label: tx("Alertes"), right: "reports.view" },
    ],
  },
  { title: tx("Audit"), items: [{ to: "/admin/audit", label: tx("Audit"), right: "audit.view" }] },
  // Own account and password: open to everyone.
  { title: tx("Général"), items: [{ to: "/admin/general", label: tx("Identifiant"), right: null }] },
];

export const MENU: MenuItem[] = MENU_SECTIONS.flatMap((section) => section.items);

const initials = (name: string | undefined) =>
  (name ?? "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";

export function AdminLayout() {
  const { user, can, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const content = useRef<HTMLElement>(null);
  useCardLabels(content);
  const newAlerts = useNewAlerts(can("reports.view"));
  const location = useLocation();
  // Close the mobile menu after navigating.
  const [lastPath, setLastPath] = useState(location.pathname);
  if (lastPath !== location.pathname) {
    setLastPath(location.pathname);
    setOpen(false);
  }

  return (
    <div className="admin">
      <aside className={`sidebar${open ? " open" : ""}`}>
        <div className="brand">
          <img src="/logo.png" alt="" />
          <div>{tx("BHH Access")}
            <small>{tx("Administration")}</small>
          </div>
        </div>
        <button className="menu-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-label={tx("Menu")}>
          {open ? tx("Fermer") : tx("Menu")}
        </button>
        <nav>
          {MENU_SECTIONS.map((section) => {
            const items = section.items.filter((item) => item.right === null || can(item.right));
            if (items.length === 0) return null;
            if (!section.title) {
              return items.map((item) => (
                <NavLink key={item.to} to={item.to} className="nav-top">
                  <NavIcon name={item.to} />{item.label}
                </NavLink>
              ));
            }
            return <NavGroup key={section.title} title={section.title} items={items} path={location.pathname}
              counts={{ "/admin/alertes": newAlerts }} />;
          })}
        </nav>
        <div className="me">
          <span className="avatar" aria-hidden="true">{initials(user?.full_name)}</span>
          <strong className="me-name" title={user?.full_name}>{user?.full_name}</strong>
          <button className="logout" onClick={signOut} title={tx("Se déconnecter")} aria-label={tx("Se déconnecter")}>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" />
            </svg>
          </button>
        </div>
      </aside>
      <main className="content" ref={content}>
        <Outlet />
      </main>
    </div>
  );
}

/** Landing screen: the first menu entry this person is allowed to open. */
export function AdminHome() {
  const { can } = useAuth();
  const first = MENU.find((item) => item.right !== null && can(item.right)) ?? MENU.find((item) => item.right === null);
  if (!first) return <p className="note error-note">{tx("Votre compte n'a accès à aucun écran d'administration.")}</p>;
  return <Navigate to={first.to} replace />;
}

/** A main menu entry that opens to show its sub-options. Opens by itself on the current page. */
function NavGroup({ title, items, path, counts }: {
  title: string; items: MenuItem[]; path: string; counts: Record<string, number>;
}) {
  const total = items.reduce((sum, item) => sum + (counts[item.to] ?? 0), 0);
  const containsCurrent = items.some((item) => path.startsWith(item.to));
  const [expanded, setExpanded] = useState(containsCurrent);
  const [lastPath, setLastPath] = useState(path);
  if (lastPath !== path) {
    setLastPath(path);
    if (containsCurrent && !expanded) setExpanded(true);
  }
  const id = `nav-${title}`;
  return (
    <div className={`nav-group${expanded ? " expanded" : ""}${containsCurrent ? " current" : ""}`}>
      <button type="button" className="nav-group-head" aria-expanded={expanded} aria-controls={id}
        onClick={() => setExpanded(!expanded)}>
        <NavIcon name={title} />
        <span>{title}</span>
        {!expanded && total > 0 && <span className="nav-count" aria-label={`${total} nouvelle(s)`}>{total}</span>}
        <svg className="chevron" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
      </button>
      {expanded && (
        <div className="nav-sub" id={id}>
          {items.map((item) => (
            <NavLink key={item.to} to={item.to}>
              {item.label}
              {(counts[item.to] ?? 0) > 0 && <span className="nav-count">{counts[item.to]}</span>}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  );
}

const ICON_PATHS: Record<string, string[]> = {
  "/admin/dashboard": ["M3 3h7v9H3z", "M14 3h7v5h-7z", "M14 12h7v9h-7z", "M3 16h7v5H3z"],
  Paramétrage: ["M4 6h16", "M4 12h16", "M4 18h16", "M8 4v4", "M16 10v4", "M10 16v4"],
  Rapport: ["M4 20V10", "M10 20V4", "M16 20v-7", "M22 20H2"],
  Audit: ["M9 11l3 3 8-8", "M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"],
  Général: ["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", "M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"],
};

function NavIcon({ name }: { name: string }) {
  const paths = ICON_PATHS[name];
  if (!paths) return null;
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {paths.map((d) => <path key={d} d={d} />)}
    </svg>
  );
}

export const ALERT_VOICE_KEY = "bhh.alerts.voice";
export const alertVoiceEnabled = () => safeStorage.get(ALERT_VOICE_KEY) !== "off";

/** Alerts still « nouvelle », refreshed every 30 s and when the page changes (menu counter, voice). */
function useNewAlerts(allowed: boolean): number {
  const { admin } = useAuth();
  const location = useLocation();
  const [count, setCount] = useState(0);
  const last = useRef<number | null>(null);
  useEffect(() => {
    if (!allowed) return undefined;
    let alive = true;
    const load = () => admin.alertCount().then(async (r) => {
      if (!alive) return;
      const before = last.current;
      last.current = r.new;
      setCount(r.new);
      // A new alert since the last check: say it aloud (can be switched off on the alerts screen).
      if (before !== null && r.new > before && alertVoiceEnabled()) {
        const [latest] = await admin.alerts("NOUVELLE", undefined, 1);
        const lang = getLang();
        if (latest && alive) speak(alertAnnouncement(latest, lang), lang);
      }
    }).catch(() => undefined);
    void load();
    const timer = window.setInterval(load, 30_000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [admin, allowed, location.pathname]);
  return allowed ? count : 0;
}

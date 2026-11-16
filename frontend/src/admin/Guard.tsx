import { tx } from "../i18n";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";

/** Hides a screen the user has no right to (the server enforces it too). */
export function Guard({ right, children }: { right: string; children: ReactNode }) {
  const { can } = useAuth();
  if (!can(right)) return <p className="note error-note">{tx("Vous n'avez pas accès à cet écran.")}</p>;
  return <>{children}</>;
}

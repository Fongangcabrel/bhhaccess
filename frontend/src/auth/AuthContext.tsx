import { tx } from "../i18n";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiClient } from "../api/client";
import { AdminApi } from "../api/admin";
import type { Me } from "../api/types";
import { safeStorage } from "../lib/storage";

const TOKEN_KEY = "bhh.token";

interface AuthState {
  admin: AdminApi;
  can: (permission: string) => boolean;
  user: Me | null;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => void;
  changePassword: (current: string, next: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => safeStorage.get(TOKEN_KEY));
  const [user, setUser] = useState<Me | null>(null);

  const signOut = useCallback(() => {
    safeStorage.remove(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // The client reads the token lazily so it always sends the current one.
  const admin = useMemo(() => new AdminApi(new ApiClient(() => safeStorage.get(TOKEN_KEY), signOut)), [signOut]);

  const can = useCallback((permission: string) => user?.permissions.includes(permission) ?? false, [user]);

  const signIn = useCallback(
    async (username: string, password: string) => {
      const { access_token } = await admin.login(username, password);
      safeStorage.set(TOKEN_KEY, access_token);
      setToken(access_token);
      setUser(await admin.me());
    },
    [admin],
  );

  const changePassword = useCallback(
    async (current: string, next: string) => {
      const { access_token } = await admin.changePassword(current, next);
      safeStorage.set(TOKEN_KEY, access_token); // the old token no longer works
      setToken(access_token);
      setUser(await admin.me());
    },
    [admin],
  );

  // Restore the session after a page reload.
  const [restoring, setRestoring] = useState(Boolean(token));
  useEffect(() => {
    if (!restoring) return;
    admin
      .me()
      .then(setUser)
      .catch(() => undefined) // a 401 already signed the user out
      .finally(() => setRestoring(false));
  }, [restoring, admin]);

  if (restoring) return <p className="center muted">{tx("Chargement…")}</p>;
  return <AuthContext.Provider value={{ admin, can, user, signIn, signOut, changePassword }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

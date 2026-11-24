import { tx } from "../i18n";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { ApiClient, bearer } from "../api/client";
import { AdminApi } from "../api/admin";
import type { Me, SessionTokens } from "../api/types";
import { safeStorage } from "../lib/storage";

const TOKEN_KEY = "bhh.token";
const REFRESH_KEY = "bhh.refresh";

function store(tokens: SessionTokens) {
  safeStorage.set(TOKEN_KEY, tokens.access_token);
  if (tokens.refresh_token) safeStorage.set(REFRESH_KEY, tokens.refresh_token);
  else safeStorage.remove(REFRESH_KEY);
}

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

  const clear = useCallback(() => {
    safeStorage.remove(TOKEN_KEY);
    safeStorage.remove(REFRESH_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // Renewal and logout go through a client without session: a refused renewal must not loop.
  const sessionApi = useMemo(() => new AdminApi(new ApiClient(() => null, () => undefined)), []);
  const renewing = useRef<Promise<boolean> | null>(null);
  const renew = useCallback(() => {
    // One renewal at a time: calls failing together all wait for the same new token.
    renewing.current ??= (async () => {
      const refreshToken = safeStorage.get(REFRESH_KEY);
      if (!refreshToken) return false;
      try {
        const tokens = await sessionApi.refresh(refreshToken);
        store(tokens);
        setToken(tokens.access_token);
        return true;
      } catch {
        return false;
      }
    })().finally(() => { renewing.current = null; });
    return renewing.current;
  }, [sessionApi]);

  const signOut = useCallback(() => {
    const refreshToken = safeStorage.get(REFRESH_KEY);
    if (refreshToken) sessionApi.logout(refreshToken).catch(() => undefined); // ends the session on the server
    clear();
  }, [sessionApi, clear]);

  // The client reads the token lazily so it always sends the current one.
  const admin = useMemo(
    () => new AdminApi(new ApiClient(() => safeStorage.get(TOKEN_KEY), clear, "/api", bearer, renew)),
    [clear, renew],
  );

  const can = useCallback((permission: string) => user?.permissions.includes(permission) ?? false, [user]);

  const signIn = useCallback(
    async (username: string, password: string) => {
      const tokens = await admin.login(username, password);
      store(tokens);
      setToken(tokens.access_token);
      setUser(await admin.me());
    },
    [admin],
  );

  const changePassword = useCallback(
    async (current: string, next: string) => {
      const tokens = await admin.changePassword(current, next);
      store(tokens); // the old session no longer works
      setToken(tokens.access_token);
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

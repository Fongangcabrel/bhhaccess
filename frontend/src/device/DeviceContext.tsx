import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiClient, deviceHeader } from "../api/client";
import { DeviceApi } from "../api/endpoints";
import { safeStorage } from "../lib/storage";

const TOKEN_KEY = "bhh.device.token";
const NAME_KEY = "bhh.device.name";
const VOICE_KEY = "bhh.device.voice";
const SETTINGS_REFRESH_MS = 2 * 60_000;

interface DeviceState {
  api: DeviceApi;
  paired: boolean;
  deviceName: string | null;
  /** Set per phone in the back-office (Téléphones). */
  voiceEnabled: boolean;
  pair: (code: string) => Promise<void>;
  unpair: () => void;
}

const DeviceContext = createContext<DeviceState | null>(null);

/** The phone's identity: paired once with a one-time code, then it scans without any login. */
export function DeviceProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => safeStorage.get(TOKEN_KEY));
  const [deviceName, setDeviceName] = useState<string | null>(() => safeStorage.get(NAME_KEY));
  const [voiceEnabled, setVoiceEnabled] = useState(() => safeStorage.get(VOICE_KEY) !== "off");

  const unpair = useCallback(() => {
    safeStorage.remove(TOKEN_KEY);
    safeStorage.remove(NAME_KEY);
    setToken(null);
    setDeviceName(null);
  }, []);

  // A revoked phone gets a 401 and falls back to the pairing screen by itself.
  const api = useMemo(
    () => new DeviceApi(new ApiClient(() => safeStorage.get(TOKEN_KEY), unpair, "/api", deviceHeader)),
    [unpair],
  );

  const pair = useCallback(
    async (code: string) => {
      const result = await api.pair(code);
      safeStorage.set(TOKEN_KEY, result.device_token);
      safeStorage.set(NAME_KEY, result.device_name);
      setToken(result.device_token);
      setDeviceName(result.device_name);
    },
    [api],
  );

  // The back-office may switch the voice on or off at any time: picked up within two minutes.
  useEffect(() => {
    if (token === null) return undefined;
    let alive = true;
    const load = () =>
      api.settings().then((s) => {
        if (!alive) return;
        safeStorage.set(VOICE_KEY, s.voice_enabled ? "on" : "off");
        setVoiceEnabled(s.voice_enabled);
      }).catch(() => undefined);
    void load();
    const timer = window.setInterval(load, SETTINGS_REFRESH_MS);
    return () => { alive = false; window.clearInterval(timer); };
  }, [api, token]);

  return (
    <DeviceContext.Provider value={{ api, paired: token !== null, deviceName, voiceEnabled, pair, unpair }}>
      {children}
    </DeviceContext.Provider>
  );
}

export function useDevice(): DeviceState {
  const context = useContext(DeviceContext);
  if (!context) throw new Error("useDevice must be used inside <DeviceProvider>");
  return context;
}

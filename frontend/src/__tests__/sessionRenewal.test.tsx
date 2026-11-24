import { fireEvent, render, screen } from "@testing-library/react";
import { ApiClient, ApiError } from "../api/client";
import type { SystemSetting } from "../api/types";

const reply = (status: number, body: unknown) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

afterEach(() => vi.unstubAllGlobals());

describe("session renewal in the API client", () => {
  it("renews once on a 401, then replays the call with the new token", async () => {
    let token = "old";
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(reply(401, { detail: "Session invalide ou expirée" }))
      .mockResolvedValueOnce(reply(200, { username: "admin" }));
    vi.stubGlobal("fetch", fetchMock);
    const renew = vi.fn(async () => { token = "new"; return true; });
    const onUnauthorized = vi.fn();

    const me = await new ApiClient(() => token, onUnauthorized, "/api", undefined, renew).get("/auth/me");
    expect(me).toEqual({ username: "admin" });
    expect(renew).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("Bearer new");
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("signs out when the session cannot be renewed, without looping", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(401, { detail: "Session expirée" })));
    const renew = vi.fn(async () => false);
    const onUnauthorized = vi.fn();
    await expect(new ApiClient(() => "old", onUnauthorized, "/api", undefined, renew).get("/auth/me"))
      .rejects.toBeInstanceOf(ApiError);
    expect(renew).toHaveBeenCalledTimes(1);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("does not renew a call made without a session (login)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(401, { detail: "Identifiants invalides" })));
    const renew = vi.fn(async () => true);
    await expect(new ApiClient(() => null, vi.fn(), "/api", undefined, renew).post("/auth/login", {}))
      .rejects.toThrow("Identifiants invalides");
    expect(renew).not.toHaveBeenCalled();
  });
});

const settings: SystemSetting[] = [
  { key: "session.access_minutes", group: "Sessions", label: "Durée d'un jeton d'accès", unit: "min",
    minimum: 1, maximum: 120, default: 15, value: 15, customised: false },
  { key: "alerts.burst_count", group: "Alertes", label: "Rafale : nombre de scans d'un badge", unit: "scans",
    minimum: 2, maximum: 100, default: 5, value: 4, customised: true },
];
const qrKeys = {
  keys: [{ key_id: "C09C", active: true, badges: 3 }, { key_id: "7A21", active: false, badges: 2 }],
  untracked: 4, unknown_key: 0,
};
const admin = {
  settings: vi.fn(async () => settings), updateSettings: vi.fn(async () => settings),
  qrKeys: vi.fn(async () => qrKeys),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

import { ConfigPage } from "../admin/pages/ConfigPage";

describe("Configuration screen", () => {
  beforeEach(() => vi.clearAllMocks());

  it("saves only what changed, and puts a setting back to its installation value", async () => {
    render(<ConfigPage />);
    const access = await screen.findByLabelText(/Durée d'un jeton d'accès/);
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
    fireEvent.change(access, { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    await vi.waitFor(() => expect(admin.updateSettings).toHaveBeenCalledWith({ "session.access_minutes": 10 }));

    expect(screen.getByText(/Valeur d'installation : 5 scans/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rétablir" }));  // only the customised one has it
    await vi.waitFor(() => expect(admin.updateSettings).toHaveBeenLastCalledWith({ "alerts.burst_count": null }));
  });

  it("shows the QR keys and how many badges still carry each one", async () => {
    render(<ConfigPage />);
    expect(await screen.findByText("C09C")).toBeInTheDocument();
    expect(screen.getByText("Active : signe les nouveaux QR")).toBeInTheDocument();
    expect(screen.getByText("Ancienne : encore acceptée au scan")).toBeInTheDocument();
    expect(screen.getByText(/4 badge\(s\) actif\(s\) imprimé\(s\) avant le suivi des clés/)).toBeInTheDocument();
    expect(screen.queryByText(/clé retirée/)).not.toBeInTheDocument();
  });
});

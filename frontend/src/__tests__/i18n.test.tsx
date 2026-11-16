import { fireEvent, render, screen } from "@testing-library/react";
import { ApiClient } from "../api/client";
import type { Scanner } from "../api/endpoints";
import type { Checkpoint, ScanResult } from "../api/types";
import { LangProvider } from "../i18n";
import { en, fr } from "../i18n/messages";
import { getLang } from "../lib/lang";

vi.mock("../features/scan/QrScanner", () => ({
  QrScanner: ({ onDetect }: { onDetect: (t: string) => void }) => <button onClick={() => onDetect("tok")}>fake-detect</button>,
}));

import { ScanPage } from "../features/scan/ScanPage";

const checkpoint: Checkpoint = {
  id: 1, name: "Entrée usine", zone_id: 1, direction: "ENTREE", zone_name: "Usine", unit_id: 1,
  unit_name: "Site A", agent_id: null, agent_name: null, is_active: true, usable: true,
};
const denied: ScanResult = {
  verdict: "REFUSE_REVOQUE", flags: [], occurred_at: "2026-11-11T08:00:00Z", log_id: 1, direction: "ENTREE",
  zone: "Usine", checkpoint: "Entrée usine",
  employee: { id: 1, matricule: "EMP-0042", last_name: "Ngono", first_name: "Paul", job_title: null },
};

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals(); });

describe("French / English on the agent's phone", () => {
  it("switches every text at once and remembers the choice", async () => {
    const api = { scanQr: vi.fn().mockResolvedValue(denied), scanManual: vi.fn() } as unknown as Scanner;
    render(<LangProvider><ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} /></LangProvider>);
    expect(screen.queryByText("Changer")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Démarrer le contrôle" }));
    expect(screen.getByText("Changer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByText("Change")).toBeInTheDocument();
    expect(screen.getByText("Entry")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Employee number (damaged QR)")).toBeInTheDocument();
    expect(getLang()).toBe("en");
    fireEvent.click(screen.getByText("fake-detect"));
    expect(await screen.findByText("BADGE REVOKED")).toBeInTheDocument();
    expect(screen.getByText("Tap to continue")).toBeInTheDocument();
  });

  it("asks the server to answer in the chosen language", async () => {
    localStorage.setItem("bhh.lang", "en");
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await new ApiClient(() => null, () => undefined).get("/device/settings");
    expect(fetchMock.mock.calls[0][1].headers["Accept-Language"]).toBe("en");
  });

  it("has an English text for every French one", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
    expect(Object.values(en).every((text) => text.trim().length > 0)).toBe(true);
  });
});

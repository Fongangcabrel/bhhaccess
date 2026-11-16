import { fireEvent, render, screen } from "@testing-library/react";
import type { Scanner } from "../api/endpoints";
import type { Checkpoint, ScanResult } from "../api/types";
import { alertAnnouncement, scanAnnouncement } from "../lib/voice";

vi.mock("../features/scan/QrScanner", () => ({
  QrScanner: ({ active, onDetect }: { active: boolean; onDetect: (t: string) => void }) => (
    <button disabled={!active} onClick={() => onDetect("tok")}>fake-detect</button>
  ),
}));

import { ScanPage } from "../features/scan/ScanPage";

const paul: ScanResult = {
  verdict: "AUTORISE", flags: [], occurred_at: "2026-11-11T08:00:00Z", log_id: 1, direction: "ENTREE",
  zone: "Usine", checkpoint: "Entrée usine",
  employee: { id: 1, matricule: "EMP-0042", last_name: "Ngono", first_name: "Paul", job_title: null },
};
const checkpoint: Checkpoint = {
  id: 1, name: "Entrée usine", zone_id: 1, direction: "ENTREE", zone_name: "Usine", unit_id: 1,
  unit_name: "Site A", agent_id: null, agent_name: null, is_active: true, usable: true,
};

describe("what the phone says", () => {
  it("entry, exit, refusal with alert, unknown QR", () => {
    expect(scanAnnouncement(paul, "fr")).toBe("Entrée autorisée. Paul Ngono.");
    expect(scanAnnouncement({ ...paul, verdict: "SORTIE_ENREGISTREE" }, "fr")).toBe("Sortie enregistrée. Paul Ngono.");
    expect(scanAnnouncement({ ...paul, verdict: "REFUSE_REVOQUE", alert: "BADGE_REVOQUE" }, "fr"))
      .toBe("Accès refusé. Badge révoqué. Paul Ngono. Alerte sécurité.");
    expect(scanAnnouncement({ ...paul, alert: "SIMULTANEE" }, "fr"))
      .toBe("Entrée autorisée. Paul Ngono. Alerte sécurité : badge déjà utilisé à un autre poste il y a peu.");
    expect(scanAnnouncement({ ...paul, verdict: "REFUSE_INVALIDE", employee: null }, "fr")).toBe("QR non reconnu.");
    expect(scanAnnouncement({ ...paul, warning: "DOUBLE_ENTREE" }, "en"))
      .toBe("Entry granted. Paul Ngono. Warning: double entry.");
  });

  it("a new alert in the back-office", () => {
    expect(alertAnnouncement({ type: "SIMULTANEE", employee_name: "Paul Ngono", checkpoint_name: "Accueil" }, "fr"))
      .toBe("Nouvelle alerte : utilisation simultanée. Paul Ngono. Accueil.");
  });
});

describe("voice at the post", () => {
  const spoken: string[] = [];
  beforeEach(() => {
    spoken.length = 0;
    class Utterance { lang = ""; rate = 1; voice = null; constructor(public text: string) {} }
    vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
    vi.stubGlobal("speechSynthesis", { cancel: vi.fn(), getVoices: () => [], speak: (u: Utterance) => spoken.push(u.text) });
  });
  afterEach(() => vi.unstubAllGlobals());

  const scan = async (voice: boolean) => {
    const api = { scanQr: vi.fn().mockResolvedValue(paul), scanManual: vi.fn() } as unknown as Scanner;
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} voice={voice} />);
    fireEvent.click(screen.getByRole("button", { name: "Démarrer le contrôle" }));
    fireEvent.click(screen.getByText("fake-detect"));
    await screen.findByText("ACCÈS AUTORISÉ");
  };

  it("starts voice from a tap before enabling camera scans", async () => {
    const api = { scanQr: vi.fn().mockResolvedValue(paul), scanManual: vi.fn() } as unknown as Scanner;
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} voice />);
    expect(screen.queryByText("fake-detect")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Matricule")).not.toBeInTheDocument();
    expect(screen.queryByText("Entrée usine")).not.toBeInTheDocument();
    expect(api.scanQr).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Démarrer le contrôle" }));
    expect(spoken).toEqual(["Contrôle démarré."]);
    expect(screen.getByText("fake-detect")).toBeEnabled();
    expect(screen.getByLabelText("Matricule")).toBeInTheDocument();
    expect(screen.getByText("Entrée usine")).toBeInTheDocument();

    fireEvent.click(screen.getByText("fake-detect"));
    await screen.findByText("ACCÈS AUTORISÉ");
    expect(spoken).toEqual(["Contrôle démarré.", "Entrée autorisée. Paul Ngono."]);
  });

  it("keeps the existing silent scan flow when voice is off", async () => {
    render(<ScanPage api={{ scanQr: vi.fn().mockResolvedValue(paul), scanManual: vi.fn() } as unknown as Scanner}
      checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    expect(screen.queryByText("fake-detect")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Démarrer le contrôle" }));
    expect(screen.getByText("fake-detect")).toBeEnabled();
  });

  it("speaks scan results when the phone has the voice on", async () => {
    await scan(true);
    expect(spoken).toEqual(["Contrôle démarré.", "Entrée autorisée. Paul Ngono."]);
  });

  it("stays silent (beep only) when the back-office switched it off", async () => {
    await scan(false);
    expect(spoken).toEqual([]);
  });
});

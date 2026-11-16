import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Scanner } from "../api/endpoints";
import type { Checkpoint, ScanResult } from "../api/types";

const checkpoint: Checkpoint = {
  id: 1, name: "Entrée usine", zone_id: 1, direction: "ENTREE", zone_name: "Usine", unit_id: 1,
  unit_name: "Site A", agent_id: 7, agent_name: "Jean Mbarga", is_active: true, usable: true,
};

const authorised: ScanResult = {
  verdict: "AUTORISE", flags: [], occurred_at: "2026-11-11T08:00:00Z", log_id: 1, direction: "ENTREE",
  zone: "Usine", checkpoint: "Entrée usine",
  employee: { id: 1, matricule: "EMP-0042", last_name: "Ngono", first_name: "Paul", job_title: "Technicien" },
};

const scanQr = vi.fn();
const scanManual = vi.fn();
const api = { scanQr, scanManual } as unknown as Scanner;

// The real scanner needs a camera: replace it with a button that "detects" a token twice.
vi.mock("../features/scan/QrScanner", () => ({
  QrScanner: ({ onDetect }: { onDetect: (t: string) => void }) => (
    <button onClick={() => { onDetect("tok"); onDetect("tok"); }}>fake-detect</button>
  ),
}));

import { ScanPage } from "../features/scan/ScanPage";

beforeEach(() => vi.clearAllMocks());

function startControl() {
  fireEvent.click(screen.getByRole("button", { name: "Démarrer le contrôle" }));
}

describe("ScanPage", () => {
  it("shows the post, its unit and the agent posted there", () => {
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    expect(screen.getByText("Entrée usine")).toBeInTheDocument();
    expect(screen.getByText(/Site A · Usine · Jean Mbarga/)).toBeInTheDocument();
  });

  it("shows a green verdict with the employee, and sends a single request for repeated frames", async () => {
    scanQr.mockResolvedValue(authorised);
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    fireEvent.click(screen.getByText("fake-detect"));
    expect(await screen.findByText("ACCÈS AUTORISÉ")).toBeInTheDocument();
    expect(screen.getByText("Paul Ngono")).toBeInTheDocument();
    expect(scanQr).toHaveBeenCalledTimes(1);
    expect(scanQr).toHaveBeenCalledWith(1, "tok");
  });

  it("shows the refusal reason and when the person came in", async () => {
    scanQr.mockResolvedValue({ ...authorised, verdict: "REFUSE_ANTIPASSBACK",
      last_entry_at: "2026-11-11T07:12:00Z", last_entry_checkpoint: "Portail atelier" });
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    fireEvent.click(screen.getByText("fake-detect"));
    expect(await screen.findByText("DÉJÀ À L'INTÉRIEUR")).toBeInTheDocument();
    expect(screen.getByText(/Entrée enregistrée à/)).toHaveTextContent("08:12");
    expect(screen.getByText(/Portail atelier/)).toBeInTheDocument();
  });

  it("warns of a double entry only when the zone asks for it", async () => {
    scanQr.mockResolvedValueOnce({ ...authorised, flags: ["DOUBLE_ENTREE"] });
    const { unmount } = render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    fireEvent.click(screen.getByText("fake-detect"));
    expect(await screen.findByText("ACCÈS AUTORISÉ")).toBeInTheDocument();
    expect(screen.queryByText(/Double entrée/)).not.toBeInTheDocument();  // journal only
    unmount();
    scanQr.mockResolvedValueOnce({ ...authorised, flags: ["DOUBLE_ENTREE"], warning: "DOUBLE_ENTREE" });
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    fireEvent.click(screen.getByText("fake-detect"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Double entrée détectée");
  });

  it("dismisses the verdict on tap", async () => {
    scanQr.mockResolvedValue(authorised);
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    fireEvent.click(screen.getByText("fake-detect"));
    fireEvent.click(await screen.findByText("Toucher pour continuer"));
    await waitFor(() => expect(screen.queryByText("ACCÈS AUTORISÉ")).not.toBeInTheDocument());
  });

  it("shows an error and lets the agent retry when the server is unreachable", async () => {
    scanQr.mockRejectedValue(new Error("Serveur injoignable. Vérifiez le Wi-Fi."));
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    fireEvent.click(screen.getByText("fake-detect"));
    expect(await screen.findByText(/Serveur injoignable/)).toBeInTheDocument();
    expect(screen.getByText("Réessayer")).toBeInTheDocument();
  });

  it("supports manual matricule entry", async () => {
    scanManual.mockResolvedValue(authorised);
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    fireEvent.change(screen.getByLabelText("Matricule"), { target: { value: "EMP-0042" } });
    fireEvent.click(screen.getByText("Valider"));
    expect(await screen.findByText("ACCÈS AUTORISÉ")).toBeInTheDocument();
    expect(scanManual).toHaveBeenCalledWith(1, "EMP-0042");
  });
});

describe("ScanPage at a single door", () => {
  const exitSide: Checkpoint = { ...checkpoint, id: 2, name: "Sortie usine", direction: "SORTIE" };

  it("switches between entry and exit in one tap", () => {
    const onSwitchSide = vi.fn();
    render(<ScanPage api={api} checkpoint={checkpoint} otherSide={exitSide} onSwitchSide={onSwitchSide}
      onChangeCheckpoint={vi.fn()} />);
    startControl();
    expect(screen.getByRole("button", { name: "Entrée", pressed: true })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sortie", pressed: false }));
    expect(onSwitchSide).toHaveBeenCalledWith(exitSide);
  });

  it("shows no switch when the zone has a single direction", () => {
    render(<ScanPage api={api} checkpoint={checkpoint} onChangeCheckpoint={vi.fn()} />);
    startControl();
    expect(screen.queryByRole("group", { name: "Sens du contrôle" })).not.toBeInTheDocument();
  });
});

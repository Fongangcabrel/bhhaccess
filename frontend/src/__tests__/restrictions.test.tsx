import { fireEvent, render, screen } from "@testing-library/react";
import type { AccessZone, ScanResult } from "../api/types";

const admin = { setRestrictions: vi.fn(async () => ({})) };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

import { RestrictionsDialog } from "../admin/AccessRestrictions";
import { ResultOverlay } from "../features/scan/ResultOverlay";

const zone: AccessZone = { id: 4, name: "Atelier", granted: true, restrictions: "", schedules: [] };

beforeEach(() => vi.clearAllMocks());

it("sets dates in Douala time and a weekday slot", async () => {
  const onDone = vi.fn();
  render(<RestrictionsDialog employeeId={7} zone={zone} onClose={vi.fn()} onDone={onDone} />);
  fireEvent.change(screen.getByLabelText("À partir du"), { target: { value: "2026-11-15" } });
  fireEvent.change(screen.getByLabelText("Jusqu'au (inclus)"), { target: { value: "2026-11-30" } });
  fireEvent.click(screen.getByRole("button", { name: "+ Ajouter une plage" }));
  fireEvent.click(screen.getByRole("button", { name: "vendredi" }));  // Mon-Thu only
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  expect(admin.setRestrictions).toHaveBeenCalledWith(7, 4, {
    valid_from: "2026-11-15T00:00:00+01:00", valid_until: "2026-11-30T23:59:59+01:00",
    schedules: [{ weekdays: [1, 2, 3, 4], start: "07:00", end: "18:00" }],
  });
  await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
});

it("explains a night slot and refuses a slot without any day", () => {
  render(<RestrictionsDialog employeeId={7} zone={{ ...zone, schedules: [{ weekdays: [6], start: "22:00:00", end: "06:00:00" }] }}
    onClose={vi.fn()} onDone={vi.fn()} />);
  expect(screen.getByText(/se termine le lendemain matin/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "samedi" }));
  expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
});

it("shows the agent why the zone is refused", () => {
  const result: ScanResult = {
    verdict: "REFUSE_ZONE", flags: [], occurred_at: "2026-11-12T08:00:00Z", log_id: 1, direction: "ENTREE",
    zone: "Atelier", checkpoint: "Portail", employee: null, detail: "Hors des horaires autorisés : lun–ven 07:00–18:00",
  };
  render(<ResultOverlay result={result} onDismiss={vi.fn()} />);
  expect(screen.getByText("Hors des horaires autorisés : lun–ven 07:00–18:00")).toBeInTheDocument();
  expect(screen.queryByText("Cette personne n'a pas accès ici.")).not.toBeInTheDocument();
});

import { fireEvent, render, screen } from "@testing-library/react";
import type { PhotoPurgeRequest, PurgeRequest } from "../api/types";

const result = (body: { dry_run?: boolean }) => ({ deleted: 12, dry_run: !!body.dry_run, filters: [] });
const admin = {
  employees: vi.fn(async () => [{ id: 1, first_name: "Paul", last_name: "Ngono", matricule: "E1" }]),
  entities: vi.fn(async () => [{ id: 5, name: "BHH Industrie" }]),
  departments: vi.fn(async () => [{ id: 10, name: "Production" }]),
  zones: vi.fn(async () => [{ id: 20, name: "Atelier" }]),
  purge: vi.fn(async (body: PurgeRequest) => result(body)),
  purgePhotos: vi.fn(async (body: PhotoPurgeRequest) => result(body)),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

import { PurgeDialog } from "../admin/Purge";

beforeEach(() => vi.clearAllMocks());

it("counts the journal lines, shows the summary, and deletes only after an explicit confirmation", async () => {
  const onDone = vi.fn();
  render(<PurgeDialog start={{ zone_id: "20" }} onClose={vi.fn()} onDone={onDone} />);
  await screen.findByRole("option", { name: "Production" });
  fireEvent.change(screen.getByLabelText("Département"), { target: { value: "10" } });
  fireEvent.click(screen.getByRole("button", { name: "Compter" }));
  expect(await screen.findByText("passage(s) concerné(s).", { exact: false })).toBeInTheDocument();
  expect(admin.purge).toHaveBeenCalledWith(expect.objectContaining({ department_id: 10, zone_id: 20, dry_run: true }));
  expect(screen.getByText("Département : Production")).toBeInTheDocument();
  expect(screen.getByText("Zone : Atelier")).toBeInTheDocument();

  const remove = screen.getByRole("button", { name: "Supprimer définitivement" });
  expect(remove).toBeDisabled(); // not confirmed yet
  fireEvent.click(screen.getByLabelText("Je confirme la suppression définitive de ces 12 passage(s)"));
  fireEvent.click(remove);
  expect(await screen.findByText("passage(s) supprimé(s).", { exact: false })).toBeInTheDocument();
  expect(admin.purge).toHaveBeenLastCalledWith(expect.objectContaining({ department_id: 10, zone_id: 20, dry_run: false }));
});

it("changing a filter after counting asks to count again", async () => {
  render(<PurgeDialog start={{ department_id: "10" }} onClose={vi.fn()} onDone={vi.fn()} />);
  await screen.findByRole("option", { name: "Atelier" });
  fireEvent.click(screen.getByRole("button", { name: "Compter" }));
  await screen.findByText("passage(s) concerné(s).", { exact: false });
  fireEvent.change(screen.getByLabelText("Zone"), { target: { value: "20" } });
  expect(screen.getByRole("button", { name: "Compter" })).toBeInTheDocument();
});

it("removes the photos of archived employees in bulk", async () => {
  render(<PurgeDialog onClose={vi.fn()} onDone={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: "Photos des employés" }));
  expect(screen.getByRole("button", { name: "Compter" })).toBeDisabled(); // no filter yet
  fireEvent.click(screen.getByLabelText("Employés archivés seulement"));
  fireEvent.click(screen.getByRole("button", { name: "Compter" }));
  await screen.findByText("photo(s) concerné(s).", { exact: false });
  fireEvent.click(screen.getByLabelText("Je confirme la suppression définitive de ces 12 photo(s)"));
  fireEvent.click(screen.getByRole("button", { name: "Supprimer définitivement" }));
  expect(await screen.findByText("photo(s) supprimée(s).", { exact: false })).toBeInTheDocument();
  expect(admin.purgePhotos).toHaveBeenLastCalledWith({ archived_only: true, dry_run: false, department_id: undefined, entity_id: undefined });
  expect(admin.purge).not.toHaveBeenCalled();
});

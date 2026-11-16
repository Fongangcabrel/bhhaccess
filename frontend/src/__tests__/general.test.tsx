import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const changePassword = vi.fn(async () => undefined);
const user = { id: 1, username: "admin", full_name: "Awa Mballa", role: "super_admin", permissions: [], must_change_password: false };
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user, changePassword, signOut: vi.fn(), can: (right: string) => right === "employees.view" }),
}));

import { AdminLayout } from "../admin/AdminLayout";
import { GeneralPage } from "../admin/pages/GeneralPage";

beforeEach(() => vi.clearAllMocks());

it("shows the account with a readable role and changes the password", async () => {
  render(<GeneralPage />);
  expect(screen.getByText("Super administrateur")).toBeInTheDocument();
  expect(screen.getByText("admin")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Mot de passe actuel"), { target: { value: "Ancien-2026" } });
  fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), { target: { value: "Nouveau-2026" } });
  fireEvent.change(screen.getByLabelText("Confirmer le nouveau mot de passe"), { target: { value: "Nouveau-2026" } });
  fireEvent.click(screen.getByRole("button", { name: "Changer le mot de passe" }));
  expect(changePassword).toHaveBeenCalledWith("Ancien-2026", "Nouveau-2026");
  expect(await screen.findByRole("status")).toHaveTextContent("Mot de passe modifié");
  expect(screen.getByLabelText("Mot de passe actuel")).toHaveValue("");  // form emptied
});

it("menu by section: « Identifiant » (Général) for everyone, clean footer without the technical role", () => {
  render(
    <MemoryRouter initialEntries={["/admin/general"]}>
      <Routes><Route path="/admin/*" element={<AdminLayout />} /></Routes>
    </MemoryRouter>,
  );
  // The menu holding the current page is open; the others are closed until clicked.
  expect(screen.getByRole("button", { name: "Général" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: "Identifiant" })).toBeInTheDocument();
  const settings = screen.getByRole("button", { name: "Paramétrage" });
  expect(settings).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("link", { name: "Employés" })).not.toBeInTheDocument();
  fireEvent.click(settings);
  expect(screen.getByRole("link", { name: "Employés" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Rapport" })).not.toBeInTheDocument();  // nothing allowed inside
  expect(screen.queryByRole("link", { name: "Utilisateurs" })).not.toBeInTheDocument();
  expect(screen.getByText("AM")).toBeInTheDocument();
  expect(screen.queryByText("super_admin")).not.toBeInTheDocument();
  expect(screen.queryByText("Mon mot de passe")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Se déconnecter" })).toBeInTheDocument();
});

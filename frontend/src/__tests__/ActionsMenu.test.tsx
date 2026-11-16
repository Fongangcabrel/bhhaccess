import { fireEvent, render, screen } from "@testing-library/react";
import { ActionsMenu } from "../admin/components/ui";

it("opens, runs an action, then closes", () => {
  const edit = vi.fn();
  render(<ActionsMenu label="Atelier" actions={[
    { label: "Modifier la zone", onClick: edit },
    { label: "Supprimer la zone", onClick: vi.fn(), danger: true, disabled: true, hint: "Historique" },
  ]} />);
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Actions : Atelier" }));
  expect(screen.getByRole("menuitem", { name: "Supprimer la zone" })).toBeDisabled();
  fireEvent.click(screen.getByRole("menuitem", { name: "Modifier la zone" }));
  expect(edit).toHaveBeenCalledOnce();
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});

it("closes with Escape", () => {
  render(<ActionsMenu label="Poste" actions={[{ label: "Modifier", onClick: vi.fn() }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Actions : Poste" }));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});
